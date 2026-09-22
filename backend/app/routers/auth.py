"""Rutas de autenticación de CampusCloud."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.excepciones import ErrorNoAutorizado, ErrorProhibido
from app.models import Usuario, Rol, Estado
from app.schemas import LoginIn, RegistroIn, TokenOut
from app.security import crear_token, verificar_password, hash_password


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)


@router.post("/registro", status_code=201)
def registro(
    datos: RegistroIn,
    db: Session = Depends(get_db),
):
    email = datos.email.strip().lower()
    dni = datos.dni.strip()
    rol_nombre = datos.rol.strip().upper()

    # Verificar si el email ya está registrado
    usuario_email = db.scalar(
        select(Usuario).where(Usuario.email == email)
    )

    if usuario_email is not None:
        raise HTTPException(
            status_code=409,
            detail="El email ya está registrado",
        )

    # Verificar si el DNI ya está registrado
    usuario_dni = db.scalar(
        select(Usuario).where(Usuario.dni == dni)
    )

    if usuario_dni is not None:
        raise HTTPException(
            status_code=409,
            detail="El DNI ya está registrado",
        )

    # El registro público solo permite estos roles
    if rol_nombre not in ("ALUMNO", "DOCENTE"):
        raise HTTPException(
            status_code=400,
            detail="El rol debe ser ALUMNO o DOCENTE",
        )

    # Buscar el rol en la base de datos
    rol = db.scalar(
        select(Rol).where(Rol.nombre == rol_nombre)
    )

    if rol is None:
        raise HTTPException(
            status_code=400,
            detail="El rol seleccionado no existe",
        )

    # Todo usuario nuevo queda pendiente
    estado_pendiente = db.scalar(
        select(Estado).where(Estado.nombre == "PENDIENTE")
    )

    if estado_pendiente is None:
        raise HTTPException(
            status_code=500,
            detail="No existe el estado PENDIENTE en la base de datos",
        )

    # Crear el usuario
    nuevo_usuario = Usuario(
        nombre=datos.nombre.strip(),
        apellido=datos.apellido.strip(),
        dni=dni,
        email=email,
        password_hash=hash_password(datos.password),
        id_rol=rol.id,
        id_estado=estado_pendiente.id,
        fecha_registro=datetime.now(timezone.utc),
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return {
        "mensaje": "Tu registro fue enviado a revisión",
        "id_usuario": nuevo_usuario.id,
        "estado": estado_pendiente.nombre,
    }


@router.post("/login", response_model=TokenOut)
def login(
    datos: LoginIn,
    db: Session = Depends(get_db),
):
    email = datos.email.strip().lower()

    usuario = db.scalar(
        select(Usuario).where(Usuario.email == email)
    )

    if usuario is None:
        raise ErrorNoAutorizado("Email o contraseña incorrectos")

    if not verificar_password(datos.password, usuario.password_hash):
        raise ErrorNoAutorizado("Email o contraseña incorrectos")

    if usuario.estado.nombre != "ACTIVO":
        raise ErrorProhibido("Cuenta no activada")

    token = crear_token(usuario.id)

    return TokenOut(
        access_token=token,
        token_type="bearer",
    )
