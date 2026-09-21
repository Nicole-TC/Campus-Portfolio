"""Valida la firma y el vencimiento del JWT."""
from typing import Any

from jose import JWTError, jwt

from app.config import settings
from app.excepciones import ErrorNoAutorizado


def decodificar_token(token: str) -> dict[str, Any]:
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
        payload["id_usuario"] = int(id_crudo)
    except (TypeError, ValueError):
        raise ErrorNoAutorizado("Token inválido")

    return payload
