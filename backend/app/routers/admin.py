"""Endpoints de administración — Módulo de aprobación de usuarios (G-9).

Todos los endpoints requieren rol ADMIN: la dependencia `require_admin`
está aplicada a nivel de router para no repetirla en cada función.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.schemas import (
    AprobarUsuarioIn,
    CatalogoOut,
    RolAdminOut,
    UsuarioPendienteOut,
    UsuarioResueltoOut,
)
from app.services import admin as admin_service

router = APIRouter(
    prefix="/admin",
    tags=["Administración"],
    dependencies=[Depends(require_admin)],
)


# ---------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------

@router.get("/roles", response_model=list[RolAdminOut])
def catalogo_roles(db: Session = Depends(get_db)):
    """Roles disponibles con sus límites base.

    El front lo usa para poblar el select al aprobar una cuenta.
    """
    return admin_service.listar_roles(db)


@router.get("/estados", response_model=list[CatalogoOut])
def catalogo_estados(db: Session = Depends(get_db)):
    """Estados de usuario disponibles (PENDIENTE, ACTIVO, RECHAZADO)."""
    return admin_service.listar_estados(db)


# ---------------------------------------------------------------
# Aprobación de usuarios
# ---------------------------------------------------------------

@router.get("/usuarios/pendientes", response_model=list[UsuarioPendienteOut])
def listar_pendientes(db: Session = Depends(get_db)):
    """Usuarios registrados esperando aprobación.

    Devuelve la lista ordenada del más viejo al más nuevo, con el rol
    que el usuario solicitó al registrarse.
    """
    return admin_service.listar_pendientes(db)


@router.patch("/usuarios/{usuario_id}/aprobar", response_model=UsuarioResueltoOut)
def aprobar(
    usuario_id: int,
    payload: AprobarUsuarioIn,
    db: Session = Depends(get_db),
):
    """Aprueba una cuenta: fija el rol final y cambia el estado a ACTIVO.

    El body debe incluir `id_rol` con el rol decidido por el admin, que
    puede coincidir o no con el rol solicitado en el registro.
    """
    return admin_service.aprobar_usuario(usuario_id, payload.id_rol, db)


@router.patch("/usuarios/{usuario_id}/rechazar", response_model=UsuarioResueltoOut)
def rechazar(usuario_id: int, db: Session = Depends(get_db)):
    """Rechaza una cuenta: cambia el estado a RECHAZADO.

    El usuario rechazado no podrá iniciar sesión (lo valida get_current_user
    al exigir estado ACTIVO).
    """
    return admin_service.rechazar_usuario(usuario_id, db)