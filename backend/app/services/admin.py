"""Lógica de negocio del módulo de administración.

G-9: aprobación de usuarios (listar pendientes, aprobar, rechazar) + catálogos.
G-14: gestión de cuotas, cambio de rol y extensiones prohibidas/bloqueadas.
"""
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.excepciones import ErrorNoEncontrado, ErrorValidacion
from app.models import (
    Archivo,
    Estado,
    Extension,
    Rol,
    RolExtensionBloqueada,
    Usuario,
    UsuarioExtensionProhibida,
)
from app.services.perfil import BYTES_POR_MB, bytes_usados, cuota_y_limite_mb
from app.services.telegram import avisar_resolucion

ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_ACTIVO = "ACTIVO"
ESTADO_RECHAZADO = "RECHAZADO"


# ---------------------------------------------------------------
# Catálogos (para que el front resuelva IDs)
# ---------------------------------------------------------------

def listar_roles(db: Session) -> list[Rol]:
    """Todos los roles del sistema, ordenados por id."""
    return list(db.scalars(select(Rol).order_by(Rol.id)))


def listar_estados(db: Session) -> list[Estado]:
    """Todos los estados de usuario, ordenados por id."""
    return list(db.scalars(select(Estado).order_by(Estado.id)))


def listar_extensiones(db: Session) -> list[Extension]:
    """Catálogo completo de extensiones soportadas."""
    return list(db.scalars(select(Extension).order_by(Extension.nombre)))


# ---------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------

def _estado_por_nombre(nombre: str, db: Session) -> Estado:
    """Busca un estado por nombre. Si no existe, es un error de configuración
    de la base (los seed deberían estar cargados)."""
    estado = db.scalar(select(Estado).where(Estado.nombre == nombre))
    if estado is None:
        raise ErrorValidacion(f"Estado '{nombre}' no existe en el catálogo")
    return estado


def _a_pendiente_out(usuario: Usuario) -> dict:
    """Serializa un Usuario al formato que espera UsuarioPendienteOut."""
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "dni": usuario.dni,
        "email": usuario.email,
        "telegram_id": usuario.telegram_id,
        "rol_solicitado": usuario.rol.nombre,
        "fecha_registro": usuario.fecha_registro,
    }


def _a_resuelto_out(usuario: Usuario) -> dict:
    """Igual que _a_pendiente_out pero agrega el rol y estado finales."""
    return _a_pendiente_out(usuario) | {
        "rol": usuario.rol.nombre,
        "estado": usuario.estado.nombre,
    }


def _a_cuota_out(usuario: Usuario, db: Session) -> dict:
    """Serializa un Usuario al formato UsuarioCuotaOut (G-14)."""
    cuota_mb, max_mb = cuota_y_limite_mb(usuario)
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "email": usuario.email,
        "rol": usuario.rol.nombre,
        "estado": usuario.estado.nombre,
        "cuota_personalizada_mb": usuario.cuota_personalizada_mb,
        "max_file_personalizado_mb": usuario.max_file_personalizado_mb,
        "cuota_efectiva_mb": cuota_mb,
        "max_file_efectivo_mb": max_mb,
        "uso_bytes": bytes_usados(usuario.id, db),
    }


# ===============================================================
# G-9: Aprobación de usuarios
# ===============================================================

# ---------------------------------------------------------------
# Pendientes
# ---------------------------------------------------------------

def listar_pendientes(db: Session) -> list[dict]:
    """Usuarios en estado PENDIENTE, del más viejo al más nuevo.

    El orden ascendente por fecha_registro hace que el admin atienda primero
    a quien esperó más tiempo.
    """
    estado_pendiente = _estado_por_nombre(ESTADO_PENDIENTE, db)
    usuarios = (
        db.scalars(
            select(Usuario)
            .options(joinedload(Usuario.rol), joinedload(Usuario.estado))
            .where(Usuario.id_estado == estado_pendiente.id)
            .order_by(Usuario.fecha_registro.asc())
        )
        .unique()
        .all()
    )
    return [_a_pendiente_out(u) for u in usuarios]


# ---------------------------------------------------------------
# Aprobar / rechazar
# ---------------------------------------------------------------

def aprobar_usuario(usuario_id: int, id_rol: int, db: Session) -> dict:
    """Aprueba una cuenta: fija el rol final y cambia el estado a ACTIVO.

    Reglas:
    - Solo se pueden aprobar cuentas en estado PENDIENTE.
    - El rol debe existir en el catálogo.
    """
    usuario = db.get(
        Usuario,
        usuario_id,
        options=[joinedload(Usuario.rol), joinedload(Usuario.estado)],
    )
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")

    if usuario.estado.nombre != ESTADO_PENDIENTE:
        raise ErrorValidacion(
            f"Solo se pueden aprobar usuarios PENDIENTES "
            f"(estado actual: {usuario.estado.nombre})."
        )

    rol = db.get(Rol, id_rol)
    if rol is None:
        raise ErrorValidacion("Rol inválido")

    usuario.id_rol = id_rol
    usuario.id_estado = _estado_por_nombre(ESTADO_ACTIVO, db).id
    chat_id = usuario.telegram_id
    db.commit()
    db.refresh(usuario)
    avisar_resolucion(chat_id, aprobado=True)
    return _a_resuelto_out(usuario)


def rechazar_usuario(usuario_id: int, db: Session, motivo: Optional[str] = None) -> dict:
    """Rechaza una cuenta: cambia el estado a RECHAZADO.

    Reglas:
    - Solo se pueden rechazar cuentas en estado PENDIENTE.

    Nota: el motivo del rechazo no se persiste (la tabla usuarios no tiene
    columna para eso). Si en el futuro se necesita, es un cambio de schema.
    """
    usuario = db.get(
        Usuario,
        usuario_id,
        options=[joinedload(Usuario.rol), joinedload(Usuario.estado)],
    )
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")

    if usuario.estado.nombre != ESTADO_PENDIENTE:
        raise ErrorValidacion(
            f"Solo se pueden rechazar usuarios PENDIENTES "
            f"(estado actual: {usuario.estado.nombre})."
        )

    usuario.id_estado = _estado_por_nombre(ESTADO_RECHAZADO, db).id
    chat_id = usuario.telegram_id
    db.commit()
    db.refresh(usuario)
    avisar_resolucion(chat_id, aprobado=False, motivo=motivo)
    return _a_resuelto_out(usuario)


# ===============================================================
# G-14: Gestión de cuotas, roles y extensiones
# ===============================================================

# ---------------------------------------------------------------
# Cuota individual por usuario
# ---------------------------------------------------------------

def actualizar_cuota_usuario(
    usuario_id: int,
    cuota_mb: Optional[int],
    max_mb: Optional[int],
    db: Session,
) -> dict:
    """Setea (o limpia) los overrides de cuota y max archivo de un usuario.

    Reglas:
    - Si un campo es None, se borra el override (hereda del rol).
    - La cuota mínima es 1 MB. El max archivo debe ser ≥ 1 MB.
    - Si max_mb > cuota_mb (cuando ambos vienen seteados), se rechaza.
    - Si la cuota nueva es menor que el uso actual, se rechaza.
    """
    usuario = db.get(
        Usuario,
        usuario_id,
        options=[joinedload(Usuario.rol), joinedload(Usuario.estado)],
    )
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")

    if cuota_mb is not None and cuota_mb < 1:
        raise ErrorValidacion("La cuota mínima es 1 MB")
    if max_mb is not None and max_mb < 1:
        raise ErrorValidacion("El tamaño máximo por archivo debe ser ≥ 1 MB")

    if cuota_mb is not None:
        uso_bytes = bytes_usados(usuario_id, db)
        if uso_bytes > cuota_mb * BYTES_POR_MB:
            raise ErrorValidacion(
                f"El usuario ya usa {uso_bytes // BYTES_POR_MB} MB, "
                f"más que la cuota que querés asignar ({cuota_mb} MB)."
            )

    if cuota_mb is not None and max_mb is not None and max_mb > cuota_mb:
        raise ErrorValidacion(
            "El tamaño máximo por archivo no puede superar la cuota total"
        )

    usuario.cuota_personalizada_mb = cuota_mb
    usuario.max_file_personalizado_mb = max_mb
    db.commit()
    db.refresh(usuario)
    return _a_cuota_out(usuario, db)


# ---------------------------------------------------------------
# Cambio de rol (con validación de cuota)
# ---------------------------------------------------------------

def cambiar_rol_usuario(usuario_id: int, id_rol: int, db: Session) -> dict:
    """Cambia el rol de un usuario validando que la nueva cuota alcance.

    Regla: la cuota efectiva del nuevo rol no puede ser menor que el uso
    actual del usuario (evita que quede "sobreocupado").
    """
    usuario = db.get(
        Usuario,
        usuario_id,
        options=[joinedload(Usuario.rol), joinedload(Usuario.estado)],
    )
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")

    rol_nuevo = db.get(Rol, id_rol)
    if rol_nuevo is None:
        raise ErrorValidacion("Rol inválido")

    cuota_nueva_mb = usuario.cuota_personalizada_mb or rol_nuevo.cuota_total_mb
    uso_bytes = bytes_usados(usuario_id, db)
    if uso_bytes > cuota_nueva_mb * BYTES_POR_MB:
        raise ErrorValidacion(
            f"El rol {rol_nuevo.nombre} tiene {cuota_nueva_mb} MB de cuota, "
            f"y el usuario ya usa {uso_bytes // BYTES_POR_MB} MB. "
            f"Liberá espacio o cargá una excepción de cuota antes de cambiar el rol."
        )

    usuario.id_rol = id_rol
    db.commit()
    db.refresh(usuario)
    return _a_cuota_out(usuario, db)


# ---------------------------------------------------------------
# Cuota y max archivo por rol
# ---------------------------------------------------------------

def actualizar_rol(
    id_rol: int,
    cuota_mb: Optional[int],
    max_mb: Optional[int],
    db: Session,
) -> Rol:
    """Actualiza cuota y/o max archivo de un rol.

    Reglas:
    - Cuota ≥ 1 MB, max archivo ≥ 1 MB.
    - Max archivo ≤ cuota total (después de aplicar el cambio).
    - Si se baja la cuota, ningún usuario del rol (sin override) puede
      quedar con uso > nueva cuota.
    """
    rol = db.get(Rol, id_rol)
    if rol is None:
        raise ErrorNoEncontrado("Rol no encontrado")

    if cuota_mb is not None and cuota_mb < 1:
        raise ErrorValidacion("La cuota mínima es 1 MB")
    if max_mb is not None and max_mb < 1:
        raise ErrorValidacion("El tamaño máximo por archivo debe ser ≥ 1 MB")

    nueva_cuota = cuota_mb if cuota_mb is not None else rol.cuota_total_mb
    nuevo_max = max_mb if max_mb is not None else rol.max_file_size_mb

    if nuevo_max > nueva_cuota:
        raise ErrorValidacion(
            "El tamaño máximo por archivo no puede superar la cuota total"
        )

    if cuota_mb is not None and cuota_mb < rol.cuota_total_mb:
        afectados = _usuarios_sobreocupados_por_cambio(id_rol, cuota_mb, db)
        if afectados:
            muestra = afectados[:10]
            extra = f" (+{len(afectados) - 10} más)" if len(afectados) > 10 else ""
            raise ErrorValidacion(
                f"No se puede reducir la cuota a {cuota_mb} MB: hay "
                f"{len(afectados)} usuario(s) del rol que ya usan más espacio. "
                f"IDs: {muestra}{extra}"
            )

    if cuota_mb is not None:
        rol.cuota_total_mb = cuota_mb
    if max_mb is not None:
        rol.max_file_size_mb = max_mb

    db.commit()
    db.refresh(rol)
    return rol


def _usuarios_sobreocupados_por_cambio(
    id_rol: int,
    nueva_cuota_mb: int,
    db: Session,
) -> list[int]:
    """Usuarios del rol (sin override personalizado) que quedarían sobreocupados.

    Los que tienen `cuota_personalizada_mb` seteado no se ven afectados
    por el cambio del rol: su cuota es el override.
    """
    usuarios = db.scalars(
        select(Usuario).where(
            Usuario.id_rol == id_rol,
            Usuario.cuota_personalizada_mb.is_(None),
        )
    ).all()
    if not usuarios:
        return []

    ids = [u.id for u in usuarios]
    filas = db.execute(
        select(Archivo.usuario_id, func.coalesce(func.sum(Archivo.tamano_bytes), 0))
        .where(Archivo.usuario_id.in_(ids))
        .group_by(Archivo.usuario_id)
    ).all()
    uso_por_usuario = {uid: int(total) for uid, total in filas}

    limite_bytes = nueva_cuota_mb * BYTES_POR_MB
    return [u.id for u in usuarios if uso_por_usuario.get(u.id, 0) > limite_bytes]


# ---------------------------------------------------------------
# Extensiones prohibidas por usuario
# ---------------------------------------------------------------

def listar_extensiones_prohibidas_usuario(usuario_id: int, db: Session) -> list[Extension]:
    """Extensiones prohibidas explícitamente para un usuario."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")
    return list(
        db.scalars(
            select(Extension)
            .join(
                UsuarioExtensionProhibida,
                UsuarioExtensionProhibida.extension_id == Extension.id,
            )
            .where(UsuarioExtensionProhibida.usuario_id == usuario_id)
            .order_by(Extension.nombre)
        )
    )


def reemplazar_extensiones_prohibidas_usuario(
    usuario_id: int,
    ids_extensiones: list[int],
    db: Session,
) -> list[Extension]:
    """Reemplaza el set completo de prohibiciones de un usuario.

    Borra las existentes e inserta el set nuevo en una transacción.
    """
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNoEncontrado("Usuario no encontrado")

    ids_unicos = list(set(ids_extensiones))

    if ids_unicos:
        existentes = set(
            db.scalars(select(Extension.id).where(Extension.id.in_(ids_unicos)))
        )
        faltantes = set(ids_unicos) - existentes
        if faltantes:
            raise ErrorValidacion(f"IDs de extensión inválidos: {sorted(faltantes)}")

    db.execute(
        delete(UsuarioExtensionProhibida).where(
            UsuarioExtensionProhibida.usuario_id == usuario_id
        )
    )

    for ext_id in ids_unicos:
        db.add(UsuarioExtensionProhibida(usuario_id=usuario_id, extension_id=ext_id))

    db.commit()
    return listar_extensiones_prohibidas_usuario(usuario_id, db)


# ---------------------------------------------------------------
# Extensiones bloqueadas por rol
# ---------------------------------------------------------------

def listar_extensiones_bloqueadas_rol(id_rol: int, db: Session) -> list[Extension]:
    """Extensiones bloqueadas para un rol."""
    rol = db.get(Rol, id_rol)
    if rol is None:
        raise ErrorNoEncontrado("Rol no encontrado")
    return list(
        db.scalars(
            select(Extension)
            .join(
                RolExtensionBloqueada,
                RolExtensionBloqueada.extension_id == Extension.id,
            )
            .where(RolExtensionBloqueada.rol_id == id_rol)
            .order_by(Extension.nombre)
        )
    )


def reemplazar_extensiones_bloqueadas_rol(
    id_rol: int,
    ids_extensiones: list[int],
    db: Session,
) -> list[Extension]:
    """Reemplaza el set completo de bloqueos de un rol.

    Mismo patrón que la de usuario: borrar y reinsertar.
    """
    rol = db.get(Rol, id_rol)
    if rol is None:
        raise ErrorNoEncontrado("Rol no encontrado")

    ids_unicos = list(set(ids_extensiones))

    if ids_unicos:
        existentes = set(
            db.scalars(select(Extension.id).where(Extension.id.in_(ids_unicos)))
        )
        faltantes = set(ids_unicos) - existentes
        if faltantes:
            raise ErrorValidacion(f"IDs de extensión inválidos: {sorted(faltantes)}")

    db.execute(
        delete(RolExtensionBloqueada).where(RolExtensionBloqueada.rol_id == id_rol)
    )

    for ext_id in ids_unicos:
        db.add(RolExtensionBloqueada(rol_id=id_rol, extension_id=ext_id))

    db.commit()
    return listar_extensiones_bloqueadas_rol(id_rol, db)