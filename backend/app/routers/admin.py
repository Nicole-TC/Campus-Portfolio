"""Endpoints de administración.

G-9: aprobación de usuarios (listar pendientes, aprobar, rechazar) + catálogos.
G-14: gestión de cuotas, cambio de rol y extensiones prohibidas/bloqueadas.

Todos los endpoints requieren rol ADMIN: la dependencia `require_admin`
está aplicada a nivel de router para no repetirla en cada función.
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.schemas import (
    AprobarUsuarioIn,
    RechazarUsuarioIn,
    CambioRolIn,
    CatalogoOut,
    CuotaUsuarioIn,
    EstadisticasAdminOut,
    EstadoUsuarioIn,
    ExtensionItemOut,
    ExtensionesProhibidasIn,
    RolAdminOut,
    RolUpdateIn,
    UsuarioCuotaOut,
    UsuarioPendienteOut,
    UsuarioResueltoOut,
)
from app.services import admin as admin_service

router = APIRouter(
    prefix="/admin",
    tags=["Administración"],
    dependencies=[Depends(require_admin)],
)


# ===============================================================
# Catálogos
# ===============================================================

@router.get("/roles", response_model=list[RolAdminOut])
def catalogo_roles(db: Session = Depends(get_db)):
    """Roles disponibles con sus límites base.

    El front lo usa para poblar el select al aprobar una cuenta
    y en la sección de políticas por rol.
    """
    return admin_service.listar_roles(db)


@router.get("/estados", response_model=list[CatalogoOut])
def catalogo_estados(db: Session = Depends(get_db)):
    """Estados de usuario disponibles (PENDIENTE, ACTIVO, RECHAZADO)."""
    return admin_service.listar_estados(db)


@router.get("/extensiones", response_model=list[ExtensionItemOut])
def catalogo_extensiones(db: Session = Depends(get_db)):
    """Catálogo completo de extensiones soportadas.

    El front lo usa para los selects de extensiones permitidas/bloqueadas.
    """
    return admin_service.listar_extensiones(db)


# ===============================================================
# G-9: Aprobación de usuarios
# ===============================================================

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
def rechazar(
    usuario_id: int,
    payload: RechazarUsuarioIn = Body(default_factory=RechazarUsuarioIn),
    db: Session = Depends(get_db),
):
    """Rechaza una cuenta: cambia el estado a RECHAZADO.

    El usuario rechazado no podrá iniciar sesión (lo valida get_current_user
    al exigir estado ACTIVO). Si hay Telegram vinculado, se le avisa.
    El motivo es opcional y solo viaja en ese mensaje.
    """
    return admin_service.rechazar_usuario(usuario_id, db, motivo=payload.motivo)


@router.get("/usuarios", response_model=list[UsuarioCuotaOut])
def listar_usuarios(
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lista usuarios registrados (excluye pendientes por defecto)."""
    return admin_service.listar_usuarios(db, estado=estado)


@router.get("/estadisticas", response_model=EstadisticasAdminOut)
def obtener_estadisticas(db: Session = Depends(get_db)):
    """Métricas globales consolidadas para el panel de administración."""
    return admin_service.obtener_estadisticas(db)


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioCuotaOut)
def cambiar_estado(
    usuario_id: int,
    payload: EstadoUsuarioIn,
    db: Session = Depends(get_db),
):
    """Permite suspender o reactivar a un usuario (cambia estado a ACTIVO o RECHAZADO)."""
    return admin_service.cambiar_estado_usuario(usuario_id, payload.estado, db)


# ===============================================================
# G-14: Gestión de cuotas, roles y extensiones
# ===============================================================

# ---------------------------------------------------------------
# Cuota y max archivo por rol
# ---------------------------------------------------------------

@router.patch("/roles/{id_rol}", response_model=RolAdminOut)
def actualizar_rol(
    id_rol: int,
    payload: RolUpdateIn,
    db: Session = Depends(get_db),
):
    """Actualiza la cuota y/o el max archivo de un rol.

    - Ambos campos del body son opcionales (podés mandar solo uno).
    - Valida que max archivo ≤ cuota total.
    - Si se baja la cuota, ningún usuario del rol (sin override) puede
      quedar con uso mayor a la nueva cuota.
    """
    return admin_service.actualizar_rol(
        id_rol,
        payload.cuota_total_mb,
        payload.max_file_size_mb,
        db,
    )


# ---------------------------------------------------------------
# Cuota individual por usuario
# ---------------------------------------------------------------

@router.patch("/usuarios/{usuario_id}/cuota", response_model=UsuarioCuotaOut)
def actualizar_cuota(
    usuario_id: int,
    payload: CuotaUsuarioIn,
    db: Session = Depends(get_db),
):
    """Setea o limpia los overrides de cuota del usuario.

    Si el campo no viene en el JSON, no se toca. `null` vuelve al valor del rol.
    Si la cuota nueva es menor que el uso actual, rechaza con 400.
    """
    return admin_service.actualizar_cuota_usuario(
        usuario_id,
        payload.cuota_personalizada_mb,
        payload.max_file_personalizado_mb,
        payload.model_fields_set,
        db,
    )


# ---------------------------------------------------------------
# Cambio de rol
# ---------------------------------------------------------------

@router.patch("/usuarios/{usuario_id}/rol", response_model=UsuarioCuotaOut)
def cambiar_rol(
    usuario_id: int,
    payload: CambioRolIn,
    db: Session = Depends(get_db),
):
    """Cambia el rol del usuario.

    Valida que la cuota efectiva del nuevo rol alcance para lo ya almacenado.
    Si no alcanza, responde 400 con un mensaje explicativo.
    """
    return admin_service.cambiar_rol_usuario(usuario_id, payload.id_rol, db)


# ---------------------------------------------------------------
# Extensiones prohibidas por usuario
# ---------------------------------------------------------------

@router.get(
    "/usuarios/{usuario_id}/extensiones-prohibidas",
    response_model=list[ExtensionItemOut],
)
def listar_extensiones_prohibidas(usuario_id: int, db: Session = Depends(get_db)):
    """Extensiones prohibidas específicamente para un usuario.

    Son adicionales a las que ya tiene bloqueadas su rol.
    """
    return admin_service.listar_extensiones_prohibidas_usuario(usuario_id, db)


@router.put(
    "/usuarios/{usuario_id}/extensiones-prohibidas",
    response_model=list[ExtensionItemOut],
)
def reemplazar_extensiones_prohibidas(
    usuario_id: int,
    payload: ExtensionesProhibidasIn,
    db: Session = Depends(get_db),
):
    """Reemplaza el set completo de extensiones prohibidas del usuario.

    El body debe traer la lista completa de IDs (no un diff). Si viene
    vacía, se borran todas las prohibiciones del usuario.
    """
    return admin_service.reemplazar_extensiones_prohibidas_usuario(
        usuario_id, payload.ids_extensiones, db
    )


# ---------------------------------------------------------------
# Extensiones bloqueadas por rol
# ---------------------------------------------------------------

@router.get(
    "/roles/{id_rol}/extensiones-bloqueadas",
    response_model=list[ExtensionItemOut],
)
def listar_extensiones_bloqueadas(id_rol: int, db: Session = Depends(get_db)):
    """Extensiones bloqueadas para un rol.

    Se aplican a todos los usuarios con ese rol, salvo que tengan una
    prohibición individual (que solo suma, no quita).
    """
    return admin_service.listar_extensiones_bloqueadas_rol(id_rol, db)


@router.put(
    "/roles/{id_rol}/extensiones-bloqueadas",
    response_model=list[ExtensionItemOut],
)
def reemplazar_extensiones_bloqueadas(
    id_rol: int,
    payload: ExtensionesProhibidasIn,
    db: Session = Depends(get_db),
):
    """Reemplaza el set completo de extensiones bloqueadas del rol.

    El body debe traer la lista completa de IDs (no un diff). Si viene
    vacía, se borran todos los bloqueos del rol.
    """
    return admin_service.reemplazar_extensiones_bloqueadas_rol(
        id_rol, payload.ids_extensiones, db
    )