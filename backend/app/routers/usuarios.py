from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Usuario
from app.schemas import AlmacenamientoOut, CambiarPasswordIn, LimitesOut, PerfilOut
from app.security import hash_password, verificar_password
from app.services.perfil import (
    BYTES_POR_MB,
    bytes_usados,
    cuota_y_limite_mb,
    extensiones_permitidas,
    extensiones_bloqueadas,
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
            extensiones_bloqueadas=extensiones_bloqueadas(usuario, db),
        ),
    )


@router.patch("/password")
def cambiar_password(
    datos: CambiarPasswordIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite al usuario cambiar su contraseña validando previamente la actual."""
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual ingresada es incorrecta.",
        )
    if len(datos.password_nueva) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 6 caracteres.",
        )
    usuario.password_hash = hash_password(datos.password_nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada con éxito."}
