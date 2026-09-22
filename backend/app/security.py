"""Funciones de seguridad para contraseñas y JWT."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.excepciones import ErrorNoAutorizado


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Genera un hash bcrypt de la contraseña."""
    return pwd_context.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    """Comprueba si una contraseña coincide con su hash."""
    return pwd_context.verify(password, password_hash)


def crear_token(id_usuario: int) -> str:
    """Genera un JWT firmado para el usuario."""
    ahora = datetime.now(timezone.utc)

    expiracion = ahora + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(id_usuario),
        "exp": expiracion,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decodificar_token(token: str) -> dict[str, Any]:
    """Valida la firma y el vencimiento del JWT."""
    if not token or not token.strip():
        raise ErrorNoAutorizado("Falta el token de autenticación")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise ErrorNoAutorizado("Token ausente, vencido o adulterado")

    id_crudo = payload.get("sub")

    if id_crudo is None:
        raise ErrorNoAutorizado("Token inválido")

    try:
        id_usuario = int(id_crudo)
    except (TypeError, ValueError):
        raise ErrorNoAutorizado("Token inválido")

    payload["id_usuario"] = id_usuario
    return payload



