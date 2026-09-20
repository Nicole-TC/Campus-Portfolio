"""Lógica de negocio del módulo Mi Perfil: límites, cuota y extensiones."""
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Archivo,
    Extension,
    RolExtensionBloqueada,
    Usuario,
    UsuarioExtensionProhibida,
)

BYTES_POR_MB = 1024 * 1024


def cuota_y_limite_mb(usuario: Usuario) -> tuple[int, int]:
    """Cuota total y tope por archivo (MB): el valor del usuario pisa al del rol."""
    cuota = usuario.cuota_personalizada_mb
    if cuota is None:
        cuota = usuario.rol.cuota_total_mb
    max_archivo = usuario.max_file_personalizado_mb
    if max_archivo is None:
        max_archivo = usuario.rol.max_file_size_mb
    return cuota, max_archivo


def bytes_usados(usuario_id: int, db: Session) -> int:
    """Espacio ocupado por el usuario. Incluye la papelera: sigue consumiendo cuota."""
    total = db.scalar(
        select(func.coalesce(func.sum(Archivo.tamano_bytes), 0)).where(
            Archivo.usuario_id == usuario_id
        )
    )
    return int(total)


def extensiones_permitidas(usuario: Usuario, db: Session) -> List[str]:
    """Todas las extensiones del catálogo menos las bloqueadas para su rol y para él."""
    bloqueadas_rol = select(RolExtensionBloqueada.extension_id).where(
        RolExtensionBloqueada.rol_id == usuario.id_rol
    )
    bloqueadas_usuario = select(UsuarioExtensionProhibida.extension_id).where(
        UsuarioExtensionProhibida.usuario_id == usuario.id
    )
    consulta = (
        select(Extension.nombre)
        .where(Extension.id.not_in(bloqueadas_rol))
        .where(Extension.id.not_in(bloqueadas_usuario))
        .order_by(Extension.nombre)
    )
    return list(db.scalars(consulta))
