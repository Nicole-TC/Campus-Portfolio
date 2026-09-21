import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.telegram import vincular_chat

router = APIRouter(prefix="/telegram", tags=["Telegram"])


class VincularIn(BaseModel):
    dni: str
    chat_id: int


def validar_bot(x_bot_token: str = Header(...)) -> None:
    """Solo el bot puede llamar a estos endpoints: debe enviar el token de Telegram."""
    if not settings.TELEGRAM_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración con Telegram no configurada",
        )
    if not secrets.compare_digest(
        x_bot_token.encode(), settings.TELEGRAM_TOKEN.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token del bot inválido",
        )


@router.post("/vincular", dependencies=[Depends(validar_bot)])
def vincular(datos: VincularIn, db: Session = Depends(get_db)):
    """Vincula el chat de Telegram con el usuario (por DNI) para poder notificarle."""
    try:
        encontrado = vincular_chat(datos.dni, datos.chat_id, db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este Telegram ya está vinculado a otra cuenta",
        )
    if not encontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un usuario con ese DNI",
        )
    return {"vinculado": True}
