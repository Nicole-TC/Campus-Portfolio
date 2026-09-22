"""Endpoints para gestión de carpetas."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Carpeta, Usuario
from app.schemas import CarpetaCrear


router = APIRouter(
    prefix="/carpetas",
    tags=["Carpetas"],
)


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