"""Dependencia JWT: lee el Bearer, valida la firma y deja pasar la identidad."""
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.security import decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    return decodificar_token(token)
