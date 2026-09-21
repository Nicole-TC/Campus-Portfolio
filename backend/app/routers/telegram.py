import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Usuario
from app.schemas import AlmacenamientoOut
from app.services.perfil import BYTES_POR_MB, bytes_usados, cuota_y_limite_mb
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


@router.get(
    "/status",
    dependencies=[Depends(validar_bot)],
    response_model=AlmacenamientoOut,
)
def estado_almacenamiento(chat_id: int, db: Session = Depends(get_db)):
    """Devuelve la cuota usada y libre del usuario vinculado a ese chat de Telegram."""
    # El chat_id se guarda en usuarios.telegram_id al hacer /start <DNI>
    usuario = db.scalar(select(Usuario).where(Usuario.telegram_id == chat_id))
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El chat no está vinculado a ninguna cuenta",
        )

    # Cuota y consumo en bytes reutilizando la misma lógica que usa /usuarios/me
    cuota_mb, _ = cuota_y_limite_mb(usuario)
    cuota_bytes = cuota_mb * BYTES_POR_MB
    usado = bytes_usados(usuario.id, db)

    return AlmacenamientoOut(
        usado_bytes=usado,
        cuota_bytes=cuota_bytes,
        libre_bytes=max(cuota_bytes - usado, 0),
        porcentaje_usado=round(usado / cuota_bytes * 100, 2) if cuota_bytes else 100.0,
    )
