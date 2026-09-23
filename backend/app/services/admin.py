from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.excepciones import ErrorNoEncontrado, ErrorValidacion
from app.models import Estado, Rol, Usuario

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
    db.commit()
    db.refresh(usuario)
    return _a_resuelto_out(usuario)


def rechazar_usuario(usuario_id: int, db: Session) -> dict:
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
    db.commit()
    db.refresh(usuario)
    return _a_resuelto_out(usuario)