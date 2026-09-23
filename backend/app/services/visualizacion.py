"""Lógica de visualización in-app de archivos (G-15).

Determina si un archivo se puede mostrar embebido en el navegador
(inline) o si debe descargarse (attachment), y valida el acceso.
"""
import mimetypes
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.excepciones import ErrorNoEncontrado, ErrorProhibido
from app.models import Archivo, Permiso, Usuario

# Extensiones que el navegador puede renderizar embebidas.
# Todo lo que no esté acá va como attachment (descarga).
EXTENSIONES_INLINE: set[str] = {
    # Documento visualizable con visor nativo
    ".pdf",
    # Imágenes
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    # Texto plano
    ".txt", ".csv",
    # Multimedia (video/audio nativos)
    ".mp3", ".mp4",
}


def disposition_para(extension_nombre: str) -> str:
    """Devuelve 'inline' si el navegador puede mostrar el formato, 'attachment' si no."""
    return "inline" if extension_nombre.lower() in EXTENSIONES_INLINE else "attachment"


def media_type_para(nombre_original: str) -> str:
    """Deduce el Content-Type a partir del nombre del archivo.

    Usa la librería estándar; si no reconoce la extensión, cae a octet-stream.
    """
    tipo, _ = mimetypes.guess_type(nombre_original)
    return tipo or "application/octet-stream"


def obtener_archivo_visible(archivo_id: int, usuario: Usuario, db: Session) -> Archivo:
    """Devuelve el archivo si el usuario es dueño o tiene permiso sobre él.

    - 404 si el archivo no existe.
    - 403 si el usuario no es dueño ni tiene permiso.
    """
    archivo = db.get(
        Archivo,
        archivo_id,
        options=[joinedload(Archivo.extension)],
    )
    if archivo is None:
        raise ErrorNoEncontrado("El archivo no existe")

    if archivo.usuario_id == usuario.id:
        return archivo

    permiso = db.scalar(
        select(Permiso).where(
            Permiso.archivo_id == archivo_id,
            Permiso.usuario_id == usuario.id,
        )
    )
    if permiso is None:
        raise ErrorProhibido("No tenés acceso a este archivo")

    return archivo


def preparar_visualizacion(archivo_id: int, usuario: Usuario, db: Session) -> dict:
    """Devuelve todo lo necesario para servir el archivo con FileResponse.

    Retorna un dict con:
    - ruta: ruta física del archivo en disco
    - nombre_original: nombre con el que se muestra/descarga
    - media_type: Content-Type
    - disposition: 'inline' o 'attachment'
    """
    archivo = obtener_archivo_visible(archivo_id, usuario, db)

    # Verificar que el archivo físico exista antes de intentar servirlo.
    if not Path(archivo.ruta).is_file():
        raise ErrorNoEncontrado("El archivo ya no está disponible en el servidor")

    nombre_extension = archivo.extension.nombre if archivo.extension else Path(archivo.nombre_original).suffix

    return {
        "ruta": archivo.ruta,
        "nombre_original": archivo.nombre_original,
        "media_type": media_type_para(archivo.nombre_original),
        "disposition": disposition_para(nombre_extension),
    }