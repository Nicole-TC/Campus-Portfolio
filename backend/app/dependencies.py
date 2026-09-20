"""Dependencias de seguridad: validación del JWT y usuario autenticado."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Usuario

# Nombre del estado que habilita el ingreso (catálogo 'estados' de la BD)
ESTADO_ACTIVO = "ACTIVO"

bearer_scheme = HTTPBearer()


def get_current_user(
    credenciales: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Decodifica el JWT ('sub' = id del usuario) y devuelve al usuario autenticado."""
    error_401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credenciales.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        usuario_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise error_401

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise error_401
    if usuario.estado.nombre != ESTADO_ACTIVO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta no activada",
        )
    return usuario
