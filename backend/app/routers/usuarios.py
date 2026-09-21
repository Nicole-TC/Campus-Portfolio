from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Usuario
from app.schemas import AlmacenamientoOut, LimitesOut, PerfilOut
from app.services.perfil import (
    BYTES_POR_MB,
    bytes_usados,
    cuota_y_limite_mb,
    extensiones_permitidas,
)

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("/me", response_model=PerfilOut)
def mi_perfil(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Datos del usuario autenticado, su cuota de almacenamiento y sus límites de subida."""
    cuota_mb, max_archivo_mb = cuota_y_limite_mb(usuario)
    cuota_bytes = cuota_mb * BYTES_POR_MB
    usado = bytes_usados(usuario.id, db)

    return PerfilOut(
        id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        dni=usuario.dni,
        email=usuario.email,
        rol=usuario.rol.nombre,
        estado=usuario.estado.nombre,
        almacenamiento=AlmacenamientoOut(
            usado_bytes=usado,
            cuota_bytes=cuota_bytes,
            libre_bytes=max(cuota_bytes - usado, 0),
            porcentaje_usado=round(usado / cuota_bytes * 100, 2) if cuota_bytes else 100.0,
        ),
        limites=LimitesOut(
            tamano_max_archivo_bytes=max_archivo_mb * BYTES_POR_MB,
            extensiones_permitidas=extensiones_permitidas(usuario, db),
        ),
    )
