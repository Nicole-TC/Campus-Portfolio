from typing import Optional

from fastapi import Cookie, Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.security import decodificar_token
from app.excepciones import ErrorNoAutorizado, ErrorProhibido

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

ESTADO_ACTIVO = "ACTIVO"
ROL_ADMIN = "ADMIN"


def _usuario_desde_token(token: str, db: Session) -> Usuario:
    """Valida el token y devuelve el usuario. Lógica compartida entre dependencias."""
    payload = decodificar_token(token)
    usuario_id = payload.get("id_usuario")

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNoAutorizado("El usuario ya no existe")

    if usuario.estado.nombre != ESTADO_ACTIVO:
        raise ErrorProhibido("Cuenta no activada")

    return usuario


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Valida el JWT del header Authorization y devuelve el usuario autenticado.

    - 401 si el token es inválido o el usuario ya no existe.
    - 403 si la cuenta no está ACTIVA.
    """
    if not token:
        raise ErrorNoAutorizado("Falta el token de autenticación")
    return _usuario_desde_token(token, db)


def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Como get_current_user, pero además exige rol ADMIN.

    - 401 si no hay sesión (lo maneja get_current_user).
    - 403 si el usuario no tiene rol ADMIN.
    """
    if usuario.rol.nombre != ROL_ADMIN:
        raise ErrorProhibido("Se requiere rol de administrador")
    return usuario


def get_current_user_flexible(
    token_header: Optional[str] = Depends(oauth2_scheme),
    token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    token_query: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db),
) -> Usuario:
    """Igual que get_current_user, pero acepta el token por header, cookie o query.

    Se usa en endpoints que devuelven contenido embebible (<img>, <iframe>),
    donde el navegador no puede mandar el header Authorization.

    Orden de prioridad: header > cookie > query param.
    """
    token = token_header or token_cookie or token_query
    if not token:
        raise ErrorNoAutorizado("Falta el token de autenticación")
    return _usuario_desde_token(token, db)