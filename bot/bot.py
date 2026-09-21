"""
Bot de Telegram de CampusCloud.

Esto es solo el esqueleto para confirmar que el contenedor levanta bien.
El desarrollo real (comandos /espacio, /archivos, login, etc.) lo arma el equipo.

Sugerencia:
  - Usar requests para llamar a la API del backend (http://backend:8000
    dentro de la red de Docker, ya viene como variable BACKEND_URL).
  - Guardar la sesión del usuario (token JWT) asociada a su chat_id.
"""
import asyncio
import os
import logging
import re
from typing import Optional

import requests
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

# El DNI viaja en el link t.me/<bot>?start=<DNI>; usuarios.dni admite hasta 15 caracteres
DNI_REGEX = re.compile(r"^\d{1,15}$")


def _vincular_en_backend(dni: str, chat_id: int) -> Optional[int]:
    """Pide al backend guardar el chat_id del usuario. Devuelve el código HTTP o None si no responde."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/telegram/vincular",
            json={"dni": dni, "chat_id": chat_id},
            headers={"X-Bot-Token": TELEGRAM_TOKEN},
            timeout=10,
        )
        return resp.status_code
    except requests.RequestException as e:
        logger.error("No se pudo contactar al backend: %s", e)
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sin parámetro: saludo normal. Con parámetro (/start <DNI>): vinculación de cuenta.
    if not context.args:
        await update.message.reply_text("¡Hola! Soy el bot de CampusCloud. 🌥️ (en construcción)")
        return

    dni = context.args[0]
    if not DNI_REGEX.match(dni):
        await update.message.reply_text("❌ El enlace no es válido. Volvé a abrirlo desde la web de CampusCloud.")
        return

    # requests es bloqueante: se ejecuta en un hilo para no frenar al bot
    codigo = await asyncio.to_thread(_vincular_en_backend, dni, update.effective_chat.id)

    if codigo == 200:
        await update.message.reply_text(
            "✅ ¡Listo! Vinculé tu cuenta. Te avisaremos por acá cuando el administrador revise tu registro."
        )
    elif codigo == 404:
        await update.message.reply_text("❌ No encontré un registro con ese DNI. Revisá que hayas completado el formulario web.")
    elif codigo == 409:
        await update.message.reply_text("⚠️ Este Telegram ya está vinculado a otra cuenta.")
    else:
        await update.message.reply_text("⚠️ No pude completar la vinculación ahora. Intentá de nuevo en unos minutos.")


def _consultar_status_en_backend(chat_id: int) -> tuple[Optional[int], Optional[dict]]:
    """Pide al backend el consumo de cuota del chat. Devuelve (código HTTP, cuerpo) o (None, None)."""
    try:
        resp = requests.get(
            f"{BACKEND_URL}/telegram/status",
            params={"chat_id": chat_id},
            headers={"X-Bot-Token": TELEGRAM_TOKEN},
            timeout=10,
        )
    except requests.RequestException as e:
        logger.error("No se pudo contactar al backend: %s", e)
        return None, None

    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, None


def _formatear_mb(bytes_valor: int) -> str:
    """Convierte bytes a MB con 1 decimal para mostrar en Telegram."""
    return f"{bytes_valor / (1024 * 1024):.1f} MB"


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status → consumo de cuota del usuario en CampusCloud."""
    codigo, datos = await asyncio.to_thread(
        _consultar_status_en_backend, update.effective_chat.id
    )

    if codigo == 200 and datos:
        texto = (
            "📊 *Tu almacenamiento en CampusCloud*\n"
            f"• Usado: {_formatear_mb(datos['usado_bytes'])} de {_formatear_mb(datos['cuota_bytes'])}\n"
            f"• Libre: {_formatear_mb(datos['libre_bytes'])}\n"
            f"• Ocupado: {datos['porcentaje_usado']}%"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")
    elif codigo == 404:
        await update.message.reply_text(
            "❌ Tu Telegram no está vinculado. Usá /start <tu DNI> para vincular la cuenta."
        )
    else:
        await update.message.reply_text(
            "⚠️ No pude consultar tu estado ahora. Intentá de nuevo en unos minutos."
        )


async def notificar_registro(bot: Bot, chat_id: int, aprobado: bool, motivo: Optional[str] = None) -> bool:
    """
    Avisa al usuario si su registro fue aprobado o rechazado.

    Pensada para que la use el flujo del administrador cuando pulsa [Aprobar] o [Rechazar].
    Devuelve False si no se pudo entregar (por ejemplo, si el usuario bloqueó al bot).
    """
    if aprobado:
        texto = "✅ ¡Tu registro fue aprobado! Ya podés ingresar a CampusCloud."
    else:
        texto = "❌ Tu registro fue rechazado."
        if motivo:
            texto += f"\nMotivo: {motivo}"
    try:
        await bot.send_message(chat_id=chat_id, text=texto)
        return True
    except TelegramError as e:
        logger.warning("No se pudo notificar al chat %s: %s", chat_id, e)
        return False


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()


if __name__ == "__main__":
    main()
