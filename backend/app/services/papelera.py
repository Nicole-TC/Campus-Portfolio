"""Lógica de negocio de la papelera: borrado lógico, restauración y borrado definitivo."""
import logging
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.excepciones import ErrorAPI, ErrorNoEncontrado
from app.models import Archivo, Usuario

logger = logging.getLogger(__name__)


def obtener_archivo_propio(archivo_id: int, usuario: Usuario, db: Session) -> Archivo:
    """Busca el archivo filtrando por dueño: si no es suyo, se responde como si no existiera."""
    archivo = db.scalar(
        select(Archivo).where(Archivo.id == archivo_id, Archivo.usuario_id == usuario.id)
    )
    if archivo is None:
        raise ErrorNoEncontrado("El archivo no existe")
    return archivo


def enviar_a_papelera(archivo: Archivo, db: Session) -> Archivo:
    """Soft delete: no toca el disco ni borra la fila; sigue ocupando cuota."""
    if archivo.en_papelera:
        raise ErrorAPI("El archivo ya está en la papelera", 409)
    archivo.en_papelera = True
    archivo.fecha_eliminacion = func.now()
    db.commit()
    db.refresh(archivo)
    return archivo


def restaurar_de_papelera(archivo: Archivo, db: Session) -> Archivo:
    """Devuelve el archivo a la vista principal. Si su carpeta ya no existe, la BD lo deja en la raíz."""
    if not archivo.en_papelera:
        raise ErrorAPI("El archivo no está en la papelera", 409)
    archivo.en_papelera = False
    archivo.fecha_eliminacion = None
    db.commit()
    db.refresh(archivo)
    return archivo


def eliminar_definitivamente(archivo: Archivo, db: Session) -> None:
    """
    Hard delete: borra el archivo físico del disco y luego la fila en PostgreSQL.
    Solo se permite si el archivo ya está en la papelera.
    """
    if not archivo.en_papelera:
        raise ErrorAPI("Solo se puede eliminar definitivamente un archivo que está en la papelera", 409)

    try:
        os.remove(archivo.ruta)
    except FileNotFoundError:
        # El archivo ya no estaba en disco: igual se limpia el registro huérfano
        logger.warning("Archivo %s sin fichero físico en %s", archivo.id, archivo.ruta)
    except OSError as e:
        # Si el disco falla no se toca la BD, para no perder la referencia al archivo
        logger.error("No se pudo borrar %s del disco: %s", archivo.ruta, e)
        raise ErrorAPI("No se pudo borrar el archivo del disco", 500)

    db.delete(archivo)
    db.commit()
