"""Endpoints para gestión y subida de archivos."""

from datetime import datetime
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_flexible, resolver_usuario_subida
from app.models import Archivo, Carpeta, Extension, Permiso, Usuario
from app.schemas import ArchivoPapeleraOut, ElementoMover, ElementoRenombrar
from app.services.papelera import (
    eliminar_definitivamente,
    enviar_a_papelera,
    obtener_archivo_propio,
    restaurar_de_papelera,
)
from app.services.perfil import (
    BYTES_POR_MB,
    bytes_usados,
    cuota_y_limite_mb,
    extensiones_permitidas,
)
from app.services.visualizacion import preparar_visualizacion


router = APIRouter(
    prefix="/archivos",
    tags=["Archivos"],
)


@router.post("", status_code=201)
async def subir_archivo(
    archivo: UploadFile = File(...),
    carpeta_id: int | None = Form(None),
    usuario: Usuario = Depends(resolver_usuario_subida),
    db: Session = Depends(get_db),
):
    if not archivo.filename:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe tener un nombre",
        )

    # Sacar la extensión del archivo
    extension_nombre = Path(archivo.filename).suffix.lower()

    if not extension_nombre:
        raise HTTPException(
            status_code=400,
            detail="El archivo no tiene una extensión válida",
        )

    # Revisar si la extensión está permitida
    permitidas = {
        extension.lower()
        for extension in extensiones_permitidas(usuario, db)
    }

    if extension_nombre not in permitidas:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido",
        )

    # Buscar la extensión en la BD
    extension = db.scalar(
        select(Extension).where(
            Extension.nombre == extension_nombre
        )
    )

    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="La extensión no está registrada en el sistema",
        )

    # Obtener el tamaño sin cargar todo el archivo en memoria
    archivo.file.seek(0, 2)
    tamano_bytes = archivo.file.tell()
    archivo.file.seek(0)

    # Obtener cuota y tamaño máximo
    cuota_mb, max_archivo_mb = cuota_y_limite_mb(usuario)

    cuota_bytes = cuota_mb * BYTES_POR_MB
    max_archivo_bytes = max_archivo_mb * BYTES_POR_MB

    # Validar tamaño máximo
    if tamano_bytes > max_archivo_bytes:
        raise HTTPException(
            status_code=413,
            detail="El archivo supera el tamaño máximo permitido",
        )

    # Validar cuota disponible
    usado = bytes_usados(usuario.id, db)

    if usado + tamano_bytes > cuota_bytes:
        raise HTTPException(
            status_code=413,
            detail="No hay suficiente espacio disponible",
        )

    # Revisar la carpeta si se mandó una
    if carpeta_id is not None:
        carpeta = db.scalar(
            select(Carpeta).where(
                Carpeta.id == carpeta_id,
                Carpeta.usuario_id == usuario.id,
                Carpeta.en_papelera.is_(False),
            )
        )

        if carpeta is None:
            raise HTTPException(
                status_code=404,
                detail="La carpeta no existe",
            )

    # Carpeta física del usuario
    carpeta_usuario = Path("/storage/users") / str(usuario.id)
    carpeta_usuario.mkdir(parents=True, exist_ok=True)

    # Nombre seguro para guardar en disco
    nombre_disco = uuid4().hex
    ruta_archivo = carpeta_usuario / nombre_disco

    # Guardar archivo
    with ruta_archivo.open("wb") as destino:
        copyfileobj(archivo.file, destino)

    # Guardar datos en la BD
    nuevo_archivo = Archivo(
        usuario_id=usuario.id,
        carpeta_id=carpeta_id,
        id_extension=extension.id,
        nombre_disco=nombre_disco,
        nombre_original=archivo.filename,
        ruta=str(ruta_archivo),
        tamano_bytes=tamano_bytes,
        en_papelera=False,
        fecha_subida=datetime.now(),
    )

    db.add(nuevo_archivo)

    try:
        db.commit()
        db.refresh(nuevo_archivo)

    except Exception:
        db.rollback()

        if ruta_archivo.exists():
            ruta_archivo.unlink()

        raise

    return {
        "id": nuevo_archivo.id,
        "nombre": nuevo_archivo.nombre_original,
        "tamano_bytes": nuevo_archivo.tamano_bytes,
        "mensaje": "Archivo subido correctamente",
    }


@router.get("")
def listar_archivos(
    carpeta_id: int | None = None,
    q: str | None = None,
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offset = (pagina - 1) * limite

    if q and q.strip():
        termino = f"%{q.strip()}%"
        carpetas = db.scalars(
            select(Carpeta)
            .where(
                Carpeta.usuario_id == usuario.id,
                Carpeta.nombre.ilike(termino),
                Carpeta.en_papelera.is_(False),
            )
            .order_by(Carpeta.nombre)
            .offset(offset)
            .limit(limite)
        ).all()

        archivos = db.scalars(
            select(Archivo)
            .where(
                Archivo.usuario_id == usuario.id,
                Archivo.nombre_original.ilike(termino),
                Archivo.en_papelera.is_(False),
            )
            .order_by(Archivo.id.desc())
            .offset(offset)
            .limit(limite)
        ).all()
    else:
        # Si se pidió una carpeta, revisar que pertenezca al usuario
        if carpeta_id is not None:
            carpeta = db.scalar(
                select(Carpeta).where(
                    Carpeta.id == carpeta_id,
                    Carpeta.usuario_id == usuario.id,
                    Carpeta.en_papelera.is_(False),
                )
            )

            if carpeta is None:
                raise HTTPException(
                    status_code=404,
                    detail="La carpeta no existe",
                )
        else:
            # Si estamos en la raíz y el usuario aún no tiene carpetas, sembramos las iniciales de su rol
            try:
                from app.services.admin import sembrar_carpetas_iniciales
                nombre_rol = usuario.rol.nombre if usuario.rol else ""
                sembrar_carpetas_iniciales(usuario.id, nombre_rol, db)
            except Exception:
                pass

        # Carpetas de la ubicación actual
        carpetas = db.scalars(
            select(Carpeta)
            .where(
                Carpeta.usuario_id == usuario.id,
                Carpeta.carpeta_padre_id == carpeta_id,
                Carpeta.en_papelera.is_(False),
            )
            .order_by(Carpeta.nombre)
            .offset(offset)
            .limit(limite)
        ).all()

        # Archivos de la ubicación actual
        archivos = db.scalars(
            select(Archivo)
            .where(
                Archivo.usuario_id == usuario.id,
                Archivo.carpeta_id == carpeta_id,
                Archivo.en_papelera.is_(False),
            )
            .order_by(Archivo.id.desc())
            .offset(offset)
            .limit(limite)
        ).all()

    from sqlalchemy import func

    carpetas_data = []
    for carpeta in carpetas:
        cant_archivos = db.scalar(
            select(func.count(Archivo.id)).where(
                Archivo.usuario_id == usuario.id,
                Archivo.carpeta_id == carpeta.id,
                Archivo.en_papelera.is_(False),
            )
        ) or 0
        cant_subcarpetas = db.scalar(
            select(func.count(Carpeta.id)).where(
                Carpeta.usuario_id == usuario.id,
                Carpeta.carpeta_padre_id == carpeta.id,
                Carpeta.en_papelera.is_(False),
            )
        ) or 0
        carpetas_data.append({
            "id": carpeta.id,
            "nombre": carpeta.nombre,
            "carpeta_padre_id": carpeta.carpeta_padre_id,
            "fecha_creacion": carpeta.fecha_creacion,
            "cantidad_elementos": cant_archivos + cant_subcarpetas,
        })

    return {
        "pagina": pagina,
        "limite": limite,
        "carpeta_id": carpeta_id,
        "carpetas": carpetas_data,
        "archivos": [
            {
                "id": archivo.id,
                "nombre": archivo.nombre_original,
                "tamano_bytes": archivo.tamano_bytes,
                "carpeta_id": archivo.carpeta_id,
                "fecha_subida": archivo.fecha_subida,
            }
            for archivo in archivos
        ],
    }


@router.get("/{archivo_id}/descargar")
def descargar_archivo(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descarga el archivo físico del servidor."""
    from fastapi.responses import FileResponse
    archivo = db.scalar(
        select(Archivo).where(
            Archivo.id == archivo_id,
            Archivo.en_papelera.is_(False),
        )
    )
    if not archivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo no existe",
        )

    # Permitir si es propio o si fue compartido con el usuario
    if archivo.usuario_id != usuario.id:
        permiso = db.scalar(
            select(Permiso).where(
                Permiso.archivo_id == archivo.id,
                Permiso.usuario_id == usuario.id,
            )
        )
        if not permiso:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para descargar este archivo",
            )

    ruta = Path(archivo.ruta)
    if not ruta.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo físico no fue encontrado en el servidor.",
        )
    return FileResponse(
        path=str(ruta),
        filename=archivo.nombre_original,
        media_type="application/octet-stream",
    )


@router.get("/papelera")
def listar_papelera(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todos los archivos del usuario que están actualmente en la papelera."""
    archivos = db.scalars(
        select(Archivo)
        .where(
            Archivo.usuario_id == usuario.id,
            Archivo.en_papelera.is_(True),
        )
        .order_by(Archivo.fecha_eliminacion.desc())
    ).all()

    carpetas = db.scalars(
        select(Carpeta)
        .where(
            Carpeta.usuario_id == usuario.id,
            Carpeta.en_papelera.is_(True),
        )
        .order_by(Carpeta.nombre)
    ).all()

    return {
        "carpetas": [
            {
                "id": c.id,
                "nombre": c.nombre,
                "tipo": "carpeta",
                "fecha_eliminacion": c.fecha_creacion,
            }
            for c in carpetas
        ],
        "archivos": [
            {
                "id": a.id,
                "nombre": a.nombre_original,
                "tipo": "archivo",
                "tamano_bytes": a.tamano_bytes,
                "fecha_eliminacion": a.fecha_eliminacion,
            }
            for a in archivos
        ]
    }


@router.get("/{archivo_id}/ver")
def ver_archivo(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Devuelve el archivo para visualización in-app (G-15).

    - `inline` para PDF, imágenes, texto plano y multimedia.
    - `attachment` para el resto (Office, comprimidos, código, ejecutables).

    Acepta el JWT por header, cookie o query param (`?token=...`) para
    permitir embeberlo en `<img>` o `<iframe>`.

    Valida que el usuario sea dueño del archivo o tenga un permiso vigente
    en la tabla `permisos`.
    """
    info = preparar_visualizacion(archivo_id, usuario, db)

    # Codificamos el nombre según RFC 5987 para soportar caracteres no-ASCII.
    nombre_codificado = quote(info["nombre_original"])

    return FileResponse(
        path=info["ruta"],
        media_type=info["media_type"],
        headers={
            "Content-Disposition": (
                f"{info['disposition']}; filename*=UTF-8''{nombre_codificado}"
            ),
        },
    )


@router.patch("/{archivo_id}/papelera", response_model=ArchivoPapeleraOut)
def mover_a_papelera(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Borrado lógico: mueve el archivo a la papelera."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    return enviar_a_papelera(archivo, db)


@router.patch("/{archivo_id}/restaurar", response_model=ArchivoPapeleraOut)
def restaurar(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restaura un archivo desde la papelera."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    return restaurar_de_papelera(archivo, db)


@router.delete("/papelera/vaciar")
def vaciar_papelera(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina definitivamente todos los archivos en papelera del usuario."""
    archivos = db.scalars(
        select(Archivo).where(
            Archivo.usuario_id == usuario.id,
            Archivo.en_papelera.is_(True),
        )
    ).all()
    for archivo in archivos:
        eliminar_definitivamente(archivo, db)

    carpetas = db.scalars(
        select(Carpeta).where(
            Carpeta.usuario_id == usuario.id,
            Carpeta.en_papelera.is_(True),
        )
    ).all()
    for carpeta in carpetas:
        db.delete(carpeta)
    db.commit()

    return {"mensaje": "Papelera vaciada con éxito", "eliminados": len(archivos) + len(carpetas)}


@router.delete("/{archivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_definitivo(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina definitivamente el archivo."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    eliminar_definitivamente(archivo, db)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/compartidos")
def listar_compartidos(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todos los archivos que otros usuarios compartieron con el usuario logueado."""
    resultados = db.execute(
        select(
            Archivo,
            Permiso.id.label("permiso_id"),
            Permiso.fecha_compartido,
            Usuario.nombre.label("propietario_nombre"),
            Usuario.apellido.label("propietario_apellido"),
            Usuario.email.label("propietario_email"),
        )
        .join(Permiso, Permiso.archivo_id == Archivo.id)
        .join(Usuario, Usuario.id == Archivo.usuario_id)
        .where(
            Permiso.usuario_id == usuario.id,
            Archivo.en_papelera.is_(False),
        )
        .order_by(Permiso.fecha_compartido.desc())
    ).all()

    return {
        "archivos": [
            {
                "id": fila.Archivo.id,
                "permiso_id": fila.permiso_id,
                "nombre": fila.Archivo.nombre_original,
                "tamano_bytes": fila.Archivo.tamano_bytes,
                "fecha_subida": fila.Archivo.fecha_subida,
                "fecha_compartido": fila.fecha_compartido,
                "propietario_id": fila.Archivo.usuario_id,
                "propietario_nombre": f"{fila.propietario_nombre} {fila.propietario_apellido}",
                "propietario_email": fila.propietario_email,
            }
            for fila in resultados
        ]
    }


@router.patch("/{archivo_id}/renombrar")
def renombrar_archivo(
    archivo_id: int,
    datos: ElementoRenombrar,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    if archivo.en_papelera:
        raise HTTPException(
            status_code=400,
            detail="No se puede renombrar un archivo que está en la papelera",
        )

    nuevo_nombre = datos.nombre.strip()
    if not nuevo_nombre:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe tener un nombre",
        )

    # Extension original y nueva
    ext_original = Path(archivo.nombre_original).suffix.lower()
    ext_nueva = Path(nuevo_nombre).suffix.lower()

    if not ext_nueva:
        # Si el usuario no especificó extensión, conservamos la original
        nuevo_nombre = f"{nuevo_nombre}{ext_original}"
        extension_id = archivo.id_extension
    else:
        permitidas = {
            ext.lower()
            for ext in extensiones_permitidas(usuario, db)
        }
        if ext_nueva not in permitidas:
            raise HTTPException(
                status_code=400,
                detail=f"La extensión {ext_nueva} no está permitida",
            )
        ext_obj = db.scalar(
            select(Extension).where(Extension.nombre == ext_nueva)
        )
        if ext_obj is None:
            raise HTTPException(
                status_code=400,
                detail="La extensión no está registrada en el sistema",
            )
        extension_id = ext_obj.id

    # Comprobar colisión en la misma carpeta
    colision = db.scalar(
        select(Archivo).where(
            Archivo.usuario_id == usuario.id,
            Archivo.carpeta_id == archivo.carpeta_id,
            Archivo.nombre_original == nuevo_nombre,
            Archivo.en_papelera.is_(False),
            Archivo.id != archivo.id,
        )
    )
    if colision is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un archivo con ese nombre en esta carpeta",
        )

    archivo.nombre_original = nuevo_nombre
    archivo.id_extension = extension_id
    db.commit()
    db.refresh(archivo)

    return {
        "ok": True,
        "id": archivo.id,
        "nombre": archivo.nombre_original,
        "mensaje": "Archivo renombrado correctamente",
    }


@router.patch("/{archivo_id}/mover")
def mover_archivo(
    archivo_id: int,
    datos: ElementoMover,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    if archivo.en_papelera:
        raise HTTPException(
            status_code=400,
            detail="No se puede mover un archivo que está en la papelera",
        )

    nueva_carpeta_id = datos.carpeta_destino_id

    # Si se especificó una carpeta destino, validar que exista, sea del usuario y no esté en papelera
    if nueva_carpeta_id is not None:
        carpeta = db.scalar(
            select(Carpeta).where(
                Carpeta.id == nueva_carpeta_id,
                Carpeta.usuario_id == usuario.id,
                Carpeta.en_papelera.is_(False),
            )
        )
        if carpeta is None:
            raise HTTPException(
                status_code=404,
                detail="La carpeta de destino no existe",
            )

    # Validar si ya está en esa misma carpeta
    if archivo.carpeta_id == nueva_carpeta_id:
        return {
            "ok": True,
            "id": archivo.id,
            "carpeta_id": archivo.carpeta_id,
            "mensaje": "El archivo ya se encuentra en la carpeta destino",
        }

    # Validar colisión en la carpeta destino
    colision = db.scalar(
        select(Archivo).where(
            Archivo.usuario_id == usuario.id,
            Archivo.carpeta_id == nueva_carpeta_id,
            Archivo.nombre_original == archivo.nombre_original,
            Archivo.en_papelera.is_(False),
            Archivo.id != archivo.id,
        )
    )
    if colision is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un archivo con el mismo nombre en la carpeta destino",
        )

    archivo.carpeta_id = nueva_carpeta_id
    db.commit()
    db.refresh(archivo)

    return {
        "ok": True,
        "id": archivo.id,
        "nombre": archivo.nombre_original,
        "carpeta_id": archivo.carpeta_id,
        "mensaje": "Archivo movido correctamente",
    }