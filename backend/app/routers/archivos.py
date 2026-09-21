from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Usuario
from app.schemas import ArchivoPapeleraOut
from app.services.papelera import (
    eliminar_definitivamente,
    enviar_a_papelera,
    obtener_archivo_propio,
    restaurar_de_papelera,
)

router = APIRouter(prefix="/archivos", tags=["Archivos"])


@router.patch("/{archivo_id}/papelera", response_model=ArchivoPapeleraOut)
def mover_a_papelera(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Borrado lógico: marca el archivo como en_papelera y registra la fecha de eliminación."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    return enviar_a_papelera(archivo, db)


@router.patch("/{archivo_id}/restaurar", response_model=ArchivoPapeleraOut)
def restaurar(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Saca el archivo de la papelera y lo devuelve a la vista principal."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    return restaurar_de_papelera(archivo, db)


@router.delete("/{archivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_definitivo(
    archivo_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Borrado definitivo (irreversible): elimina el archivo del disco y de PostgreSQL."""
    archivo = obtener_archivo_propio(archivo_id, usuario, db)
    eliminar_definitivamente(archivo, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
