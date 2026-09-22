from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.security import decodificar_token
from app.excepciones import ErrorNoAutorizado, ErrorProhibido

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

ESTADO_ACTIVO = "ACTIVO"
ROL_ADMIN = "ADMIN"


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Valida el JWT y devuelve el usuario autenticado.

    - 401 si el token es inválido o el usuario ya no existe.
    - 403 si la cuenta no está ACTIVA.
    """
    payload = decodificar_token(token)
    usuario_id = payload.get("id_usuario")

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNoAutorizado("El usuario ya no existe")

    if usuario.estado.nombre != ESTADO_ACTIVO:
        raise ErrorProhibido("Cuenta no activada")

    return usuario


def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Como get_current_user, pero además exige rol ADMIN.

    - 401 si no hay sesión (lo maneja get_current_user).
    - 403 si el usuario no tiene rol ADMIN.
    """
    if usuario.rol.nombre != ROL_ADMIN:
        raise ErrorProhibido("Se requiere rol de administrador")
    return usuario