"""Esquemas Pydantic de entrada/salida de la API."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AlmacenamientoOut(BaseModel):
    usado_bytes: int
    cuota_bytes: int
    libre_bytes: int
    porcentaje_usado: float


class LimitesOut(BaseModel):
    tamano_max_archivo_bytes: int
    extensiones_permitidas: List[str]
    extensiones_bloqueadas: List[str] = []


class PerfilOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    dni: str
    email: str
    rol: str
    estado: str
    almacenamiento: AlmacenamientoOut
    limites: LimitesOut


class CambiarPasswordIn(BaseModel):
    password_actual: str
    password_nueva: str


class CarpetaCrear(BaseModel):
    nombre: str
    carpeta_padre_id: int | None = None


class ElementoRenombrar(BaseModel):
    nombre: str


class ElementoMover(BaseModel):
    carpeta_destino_id: int | None = None


class ArchivoPapeleraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_original: str
    en_papelera: bool
    fecha_eliminacion: Optional[datetime]


class ArchivoResumenOut(BaseModel):
    """Resumen de un archivo pensado para el bot: sin rutas ni datos internos."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_original: str
    tamano_bytes: int
    fecha_subida: datetime


class RegistroIn(BaseModel):
    nombre: str
    apellido: str
    dni: str
    email: str
    password: str
    rol: str


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PermisoCrear(BaseModel):
    archivo_id: int
    destinatario: str
    token_type: str = "bearer"


# ---------------------------------------------------------------
# G-9: Módulo de aprobación de usuarios (admin)
# ---------------------------------------------------------------

class CatalogoOut(BaseModel):
    """Ítem genérico de catálogo (roles, estados, extensiones)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class RolAdminOut(CatalogoOut):
    """Rol con sus límites base, para que el front muestre las opciones al aprobar."""
    cuota_total_mb: int
    max_file_size_mb: int
    cantidad_usuarios: Optional[int] = None


class UsuarioPendienteOut(BaseModel):
    """Datos mínimos de un usuario en estado PENDIENTE."""
    id: int
    nombre: str
    apellido: str
    dni: str
    email: str
    telegram_id: Optional[int]
    rol_solicitado: str
    fecha_registro: datetime


class AprobarUsuarioIn(BaseModel):
    """Body para aprobar una cuenta: el admin elige el rol final."""
    id_rol: int


class RechazarUsuarioIn(BaseModel):
    """Motivo opcional. No se guarda en la base: solo se manda por Telegram."""
    motivo: Optional[str] = None


class UsuarioResueltoOut(UsuarioPendienteOut):
    """Usuario ya aprobado/rechazado, con su rol y estado finales."""
    rol: str
    estado: str


# ---------------------------------------------------------------
# G-14: Gestión de cuotas, roles y extensiones (admin)
# ---------------------------------------------------------------

class CuotaUsuarioIn(BaseModel):
    """Body para setear/limpiar overrides de cuota por usuario.

    Si el campo no viene, se deja como está. `null` vuelve al valor del rol.
    """
    cuota_personalizada_mb: Optional[int] = None
    max_file_personalizado_mb: Optional[int] = None


class CambioRolIn(BaseModel):
    """Body para cambiar el rol de un usuario."""
    id_rol: int


class EstadoUsuarioIn(BaseModel):
    """Body para suspender o reactivar usuario."""
    estado: str


class UsuarioCuotaOut(BaseModel):
    """Vista de un usuario con sus cuotas efectivas y uso actual."""
    id: int
    nombre: str
    apellido: str
    dni: Optional[str] = None
    email: str
    rol: str
    estado: str
    cuota_personalizada_mb: Optional[int] = None
    max_file_personalizado_mb: Optional[int] = None
    cuota_efectiva_mb: int
    max_file_efectivo_mb: int
    uso_bytes: int
    fecha_registro: Optional[datetime] = None


class EstadisticasAdminOut(BaseModel):
    """Métricas consolidadas para el panel de administración."""
    total_usuarios: int
    nuevos_este_mes: int
    solicitudes_pendientes: int
    almacenamiento_usado_mb: float
    capacidad_servidor_mb: float


class ExtensionesProhibidasIn(BaseModel):
    """Body para reemplazar el set completo de extensiones prohibidas/bloqueadas.

    Si la lista viene vacía, se borran todas las prohibiciones.
    """
    ids_extensiones: List[int]


class ExtensionItemOut(BaseModel):
    """Extensión con su id y nombre para listados."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class RolUpdateIn(BaseModel):
    """Body para actualizar cuota y/o max archivo de un rol.

    Ambos campos son opcionales: podés mandar solo uno y el otro queda como está.
    """
    cuota_total_mb: Optional[int] = None
    max_file_size_mb: Optional[int] = None