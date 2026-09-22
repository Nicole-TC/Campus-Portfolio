"""Endpoints para gestión y subida de archivos."""

from datetime import datetime
from pathlib import Path
from shutil import copyfileobj
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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Archivo, Carpeta, Extension, Permiso, Usuario
from app.schemas import ArchivoPapeleraOut
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


router = APIRouter(
    prefix="/archivos",
    tags=["Archivos"],
)


@router.post("", status_code=201)
async def subir_archivo(
    archivo: UploadFile = File(...),
    carpeta_id: int | None = Form(None),
    usuario: Usuario = Depends(get_current_user),
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
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    offset = (pagina - 1) * limite

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

    return {
        "pagina": pagina,
        "limite": limite,
        "carpeta_id": carpeta_id,
        "carpetas": [
            {
                "id": carpeta.id,
                "nombre": carpeta.nombre,
                "carpeta_padre_id": carpeta.carpeta_padre_id,
                "fecha_creacion": carpeta.fecha_creacion,
            }
            for carpeta in carpetas
        ],
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
            Permiso.fecha_compartido,
            Usuario.nombre.label("propietario_nombre"),
            Usuario.apellido.label("propietario_apellido"),
            Usuario.email.label("propietario_email"),
        )
        .join(Permiso, Permiso.archivo_id == Archivo.id)
        .join(Usuario, Usuario.id == Archivo.usuario_id)
        .where(
            Permiso.usuario_id == usuario.id,
            Archivo.en_papelera.is_(False),  # 1. Filtra los archivos que el dueño mandó a la papelera
        )
        .order_by(Permiso.fecha_compartido.desc())
    ).all()

    return {
        "archivos": [
            {
                "id": fila.Archivo.id,
                "nombre": fila.Archivo.nombre_original,
                "tamano_bytes": fila.Archivo.tamano_bytes,
                "fecha_subida": fila.Archivo.fecha_subida,
                "fecha_compartido": fila.fecha_compartido,  # 2. Fecha en que te lo compartieron
                "propietario_id": fila.Archivo.usuario_id,
                "propietario_nombre": f"{fila.propietario_nombre} {fila.propietario_apellido}",  # 3. Nombre completo del dueño
                "propietario_email": fila.propietario_email,  # 4. Email del dueño
            }
            for fila in resultados
        ]
    }
