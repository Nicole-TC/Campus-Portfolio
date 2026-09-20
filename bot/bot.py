"""
Bot de Telegram de CampusCloud.

Esto es solo el esqueleto para confirmar que el contenedor levanta bien.
El desarrollo real (comandos /espacio, /archivos, login, etc.) lo arma el equipo.

Sugerencia:
  - Usar requests para llamar a la API del backend (http://backend:8000
    dentro de la red de Docker, ya viene como variable BACKEND_URL).
  - Guardar la sesión del usuario (token JWT) asociada a su chat_id.
"""
import os
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy el bot de CampusCloud. 🌥️ (en construcción)")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()


if __name__ == "__main__":
    main()
