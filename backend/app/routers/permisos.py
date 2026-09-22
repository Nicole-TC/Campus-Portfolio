"""Endpoints para compartir archivos."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Archivo, Permiso, Usuario
from app.schemas import PermisoCrear


router = APIRouter(
    prefix="/permisos",
    tags=["Permisos"],
)


@router.post("", status_code=201)
def compartir_archivo(
    datos: PermisoCrear,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Comprobar que el archivo exista y pertenezca al usuario
    archivo = db.scalar(
        select(Archivo).where(
            Archivo.id == datos.archivo_id,
            Archivo.usuario_id == usuario.id,
            Archivo.en_papelera.is_(False),
        )
    )

    if archivo is None:
        raise HTTPException(
            status_code=404,
            detail="El archivo no existe o no te pertenece",
        )

    destinatario_buscado = datos.destinatario.strip()

    if not destinatario_buscado:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar un correo o DNI",
        )

    # Buscar al compañero por correo o DNI
    destinatario = db.scalar(
        select(Usuario).where(
            or_(
                Usuario.email == destinatario_buscado,
                Usuario.dni == destinatario_buscado,
            )
        )
    )

    if destinatario is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró el usuario",
        )

    # Evitar compartir el archivo con uno mismo
    if destinatario.id == usuario.id:
        raise HTTPException(
            status_code=400,
            detail="No podés compartir un archivo con vos mismo",
        )

    # Comprobar si ya estaba compartido
    permiso_existente = db.scalar(
        select(Permiso).where(
            Permiso.archivo_id == archivo.id,
            Permiso.usuario_id == destinatario.id,
        )
    )

    if permiso_existente is not None:
        raise HTTPException(
            status_code=409,
            detail="El archivo ya está compartido con este usuario",
        )

    nuevo_permiso = Permiso(
        archivo_id=archivo.id,
        usuario_id=destinatario.id,
        fecha_compartido=datetime.now(),
    )

    db.add(nuevo_permiso)

    try:
        db.commit()
        db.refresh(nuevo_permiso)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="El archivo ya está compartido con este usuario",
        )

    return {
        "id": nuevo_permiso.id,
        "archivo_id": nuevo_permiso.archivo_id,
        "usuario_id": nuevo_permiso.usuario_id,
        "mensaje": "Archivo compartido correctamente",
    }