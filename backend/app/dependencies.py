from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Usuario
from app.security import decodificar_token
from app.excepciones import ErrorNoAutorizado, ErrorProhibido

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
ESTADO_ACTIVO = "ACTIVO"

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> Usuario:
    
    payload = decodificar_token(token)
    usuario_id = payload.get("id_usuario")

    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNoAutorizado("El usuario ya no existe")
        
    if usuario.estado.nombre != ESTADO_ACTIVO:
        raise ErrorProhibido("Cuenta no activada")
        
    return usuario
