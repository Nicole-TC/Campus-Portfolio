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


def _a_pendiente_out(usuario: Usuario, db: Session | None = None) -> dict:
    """Serializa un Usuario al formato que espera UsuarioPendienteOut."""
    nombre_rol = usuario.rol.nombre if (usuario.rol is not None) else ""
    if not nombre_rol and db is not None and usuario.id_rol:
        rol_obj = db.get(Rol, usuario.id_rol)
        if rol_obj:
            nombre_rol = rol_obj.nombre

    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "dni": usuario.dni,
        "email": usuario.email,
        "telegram_id": usuario.telegram_id,
        "rol_solicitado": nombre_rol,
        "fecha_registro": usuario.fecha_registro,
    }


def _a_resuelto_out(usuario: Usuario, db: Session | None = None) -> dict:
    """Igual que _a_pendiente_out pero agrega el rol y estado finales de forma segura."""
    datos = _a_pendiente_out(usuario, db)
    
    nombre_rol = usuario.rol.nombre if (usuario.rol is not None) else ""
    if not nombre_rol and db is not None and usuario.id_rol:
        rol_obj = db.get(Rol, usuario.id_rol)
        if rol_obj:
            nombre_rol = rol_obj.nombre

    nombre_estado = usuario.estado.nombre if (usuario.estado is not None) else ""
    if not nombre_estado and db is not None and usuario.id_estado:
        estado_obj = db.get(Estado, usuario.id_estado)
        if estado_obj:
            nombre_estado = estado_obj.nombre

    return datos | {
        "rol": nombre_rol,
        "estado": nombre_estado,
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

def sembrar_carpetas_iniciales(usuario_id: int, nombre_rol: str, db: Session):
    """Crea carpetas lógicas iniciales en la BD para un usuario si aún no tiene ninguna."""
    from datetime import datetime
    from app.models import Carpeta

    # Verificar si ya tiene carpetas
    carpetas_existentes = db.scalar(
        select(Carpeta).where(Carpeta.usuario_id == usuario_id).limit(1)
    )
    if carpetas_existentes is not None:
        return

    rol_upper = (nombre_rol or "").upper()
    if "DOCENTE" in rol_upper:
        nombres = ["Material de cátedra", "Exámenes", "Planificaciones"]
    elif "ALUMNO" in rol_upper:
        nombres = ["Trabajos prácticos", "Apuntes"]
    else:
        nombres = ["Documentos"]

    for nom in nombres:
        c = Carpeta(
            usuario_id=usuario_id,
            carpeta_padre_id=None,
            nombre=nom,
            en_papelera=False,
            fecha_creacion=datetime.now(),
        )
        db.add(c)
    db.commit()


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

    # Crear carpetas iniciales en la base de datos según su rol
    try:
        sembrar_carpetas_iniciales(usuario.id, rol.nombre, db)
    except Exception as e:
        print(f"[ADMIN APROBAR] Error al sembrar carpetas iniciales: {e}")

    return _a_resuelto_out(usuario, db)


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

    return _a_resuelto_out(usuario, db)