"""Lógica de negocio de la vinculación de cuentas con Telegram."""
from sqlalchemy import text
from sqlalchemy.orm import Session


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
