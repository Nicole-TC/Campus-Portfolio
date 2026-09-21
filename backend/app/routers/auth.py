"""Rutas de autenticación de CampusCloud."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.excepciones import ErrorNoAutorizado, ErrorProhibido
from app.models import Usuario
from app.schemas import LoginIn, TokenOut
from app.security import crear_token, verificar_password


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)


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