"""Lógica de negocio de la vinculación de cuentas con Telegram."""
from typing import List

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Archivo, Usuario


def vincular_chat(dni: str, chat_id: int, db: Session) -> bool:
    """
    Guarda el chat_id de Telegram en usuarios.telegram_id del usuario con ese DNI.

    Devuelve False si no existe ningún usuario con ese DNI. Si el chat_id ya está
    vinculado a otro usuario, la restricción UNIQUE de la BD lanza IntegrityError
    y el router lo traduce a 409.
    """
    resultado = db.execute(
        text("UPDATE usuarios SET telegram_id = :chat_id WHERE dni = :dni RETURNING id"),
        {"chat_id": chat_id, "dni": dni},
    )
    encontrado = resultado.first() is not None
    db.commit()
    return encontrado


def ultimos_archivos_de_chat(
    chat_id: int, db: Session, limite: int = 5
) -> tuple[bool, List[Archivo]]:
    """
    Últimos archivos activos del usuario vinculado a ese chat de Telegram.

    Devuelve (chat_vinculado, archivos). Si el chat no está vinculado a nadie,
    chat_vinculado=False y el router responde 404.
    """
    usuario = db.scalar(select(Usuario).where(Usuario.telegram_id == chat_id))
    if usuario is None:
        return False, []

    archivos = list(
        db.scalars(
            select(Archivo)
            .where(Archivo.usuario_id == usuario.id)
            .where(Archivo.en_papelera.is_(False))
            .order_by(Archivo.fecha_subida.desc())
            .limit(limite)
        )
    )
    return True, archivos


