"""Endpoints para gestión de carpetas."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Archivo, Carpeta, Usuario
from app.schemas import CarpetaCrear, ElementoMover, ElementoRenombrar


router = APIRouter(
    prefix="/carpetas",
    tags=["Carpetas"],
)


@router.get("")
def listar_carpetas_usuario(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Devuelve todas las carpetas activas del usuario para listas y selectores de destino."""
    carpetas = db.scalars(
        select(Carpeta)
        .where(
            Carpeta.usuario_id == usuario.id,
            Carpeta.en_papelera.is_(False),
        )
        .order_by(Carpeta.nombre)
    ).all()

    return [
        {
            "id": c.id,
            "nombre": c.nombre,
            "carpeta_padre_id": c.carpeta_padre_id,
        }
        for c in carpetas
    ]


@router.post("", status_code=201)
def crear_carpeta(
    datos: CarpetaCrear,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=400,
            detail="La carpeta debe tener un nombre",
        )

    # Si tiene carpeta padre, revisar que exista y sea del usuario
    if datos.carpeta_padre_id is not None:
        carpeta_padre = db.scalar(
            select(Carpeta).where(
                Carpeta.id == datos.carpeta_padre_id,
                Carpeta.usuario_id == usuario.id,
                Carpeta.en_papelera.is_(False),
            )
        )

        if carpeta_padre is None:
            raise HTTPException(
                status_code=404,
                detail="La carpeta padre no existe",
            )

    nueva_carpeta = Carpeta(
        usuario_id=usuario.id,
        carpeta_padre_id=datos.carpeta_padre_id,
        nombre=nombre,
        en_papelera=False,
        fecha_creacion=datetime.now(),
    )

    db.add(nueva_carpeta)
    db.commit()
    db.refresh(nueva_carpeta)

    return {
        "id": nueva_carpeta.id,
        "nombre": nueva_carpeta.nombre,
        "carpeta_padre_id": nueva_carpeta.carpeta_padre_id,
        "mensaje": "Carpeta creada correctamente",
    }


@router.patch("/{carpeta_id}/renombrar")
def renombrar_carpeta(
    carpeta_id: int,
    datos: ElementoRenombrar,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=400,
            detail="La carpeta debe tener un nombre",
        )

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

    # Validar colisión en la misma ubicación
    colision = db.scalar(
        select(Carpeta).where(
            Carpeta.usuario_id == usuario.id,
            Carpeta.carpeta_padre_id == carpeta.carpeta_padre_id,
            Carpeta.nombre == nombre,
            Carpeta.en_papelera.is_(False),
            Carpeta.id != carpeta.id,
        )
    )
    if colision is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una carpeta con ese nombre en esta ubicación",
        )

    carpeta.nombre = nombre
    db.commit()
    db.refresh(carpeta)

    return {
        "ok": True,
        "id": carpeta.id,
        "nombre": carpeta.nombre,
        "mensaje": "Carpeta renombrada correctamente",
    }


@router.patch("/{carpeta_id}/mover")
def mover_carpeta(
    carpeta_id: int,
    datos: ElementoMover,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    destino_id = datos.carpeta_destino_id
    if destino_id == carpeta.id:
        raise HTTPException(
            status_code=400,
            detail="No podés mover una carpeta adentro de sí misma",
        )

    if destino_id is not None:
        carpeta_destino = db.scalar(
            select(Carpeta).where(
                Carpeta.id == destino_id,
                Carpeta.usuario_id == usuario.id,
                Carpeta.en_papelera.is_(False),
            )
        )
        if carpeta_destino is None:
            raise HTTPException(
                status_code=404,
                detail="La carpeta de destino no existe",
            )

        # Evitar ciclos: comprobar que la carpeta destino no sea descendiente de la carpeta que se mueve
        actual = carpeta_destino
        visitados = set()
        while actual and actual.carpeta_padre_id is not None:
            if actual.id in visitados:
                break
            visitados.add(actual.id)
            if actual.carpeta_padre_id == carpeta.id:
                raise HTTPException(
                    status_code=400,
                    detail="No podés mover una carpeta adentro de una de sus subcarpetas",
                )
            actual = db.scalar(select(Carpeta).where(Carpeta.id == actual.carpeta_padre_id))

    # Colisión
    colision = db.scalar(
        select(Carpeta).where(
            Carpeta.usuario_id == usuario.id,
            Carpeta.carpeta_padre_id == destino_id,
            Carpeta.nombre == carpeta.nombre,
            Carpeta.en_papelera.is_(False),
            Carpeta.id != carpeta.id,
        )
    )
    if colision is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una carpeta con ese nombre en la carpeta destino",
        )

    carpeta.carpeta_padre_id = destino_id
    db.commit()
    db.refresh(carpeta)

    return {
        "ok": True,
        "id": carpeta.id,
        "nombre": carpeta.nombre,
        "carpeta_padre_id": carpeta.carpeta_padre_id,
        "mensaje": "Carpeta movida correctamente",
    }


def _marcar_papelera_recursivo(carpeta_id: int, usuario_id: int, estado: bool, db: Session):
    """Marca en papelera (o restaura) todos los archivos y subcarpetas contenidos."""
    db.execute(
        update(Archivo)
        .where(Archivo.carpeta_id == carpeta_id, Archivo.usuario_id == usuario_id)
        .values(en_papelera=estado, fecha_eliminacion=func.now() if estado else None)
    )
    subcarpetas = db.scalars(
        select(Carpeta.id).where(Carpeta.carpeta_padre_id == carpeta_id, Carpeta.usuario_id == usuario_id)
    ).all()
    for sub_id in subcarpetas:
        db.execute(
            update(Carpeta)
            .where(Carpeta.id == sub_id, Carpeta.usuario_id == usuario_id)
            .values(en_papelera=estado)
        )
        _marcar_papelera_recursivo(sub_id, usuario_id, estado, db)


@router.patch("/{carpeta_id}/papelera")
def mover_carpeta_a_papelera(
    carpeta_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    carpeta = db.scalar(
        select(Carpeta).where(
            Carpeta.id == carpeta_id,
            Carpeta.usuario_id == usuario.id,
            Carpeta.en_papelera.is_(False),
        )
    )
    if carpeta is None:
        raise HTTPException(status_code=404, detail="La carpeta no existe")

    carpeta.en_papelera = True
    _marcar_papelera_recursivo(carpeta_id, usuario.id, True, db)
    db.commit()
    db.refresh(carpeta)

    return {"ok": True, "id": carpeta.id, "nombre": carpeta.nombre, "mensaje": "Carpeta enviada a la papelera"}


@router.patch("/{carpeta_id}/restaurar")
def restaurar_carpeta(
    carpeta_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    carpeta = db.scalar(
        select(Carpeta).where(
            Carpeta.id == carpeta_id,
            Carpeta.usuario_id == usuario.id,
            Carpeta.en_papelera.is_(True),
        )
    )
    if carpeta is None:
        raise HTTPException(status_code=404, detail="La carpeta no existe")

    # Si su carpeta padre sigue en papelera, la dejamos en la raíz para que sea accesible
    if carpeta.carpeta_padre_id is not None:
        padre = db.scalar(select(Carpeta).where(Carpeta.id == carpeta.carpeta_padre_id))
        if padre is None or padre.en_papelera:
            carpeta.carpeta_padre_id = None

    carpeta.en_papelera = False
    _marcar_papelera_recursivo(carpeta_id, usuario.id, False, db)
    db.commit()
    db.refresh(carpeta)

    return {"ok": True, "id": carpeta.id, "nombre": carpeta.nombre, "mensaje": "Carpeta restaurada correctamente"}


@router.delete("/{carpeta_id}")
def eliminar_carpeta_definitivo(
    carpeta_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    carpeta = db.scalar(
        select(Carpeta).where(
            Carpeta.id == carpeta_id,
            Carpeta.usuario_id == usuario.id,
        )
    )
    if carpeta is None:
        raise HTTPException(status_code=404, detail="La carpeta no existe")

    if not carpeta.en_papelera:
        raise HTTPException(status_code=409, detail="Solo se puede eliminar definitivamente una carpeta que está en la papelera")

    from app.services.papelera import eliminar_definitivamente
    archivos = db.scalars(select(Archivo).where(Archivo.carpeta_id == carpeta_id)).all()
    for a in archivos:
        eliminar_definitivamente(a, db)

    db.delete(carpeta)
    db.commit()

    return {"ok": True, "mensaje": "Carpeta eliminada definitivamente"}