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

class CarpetaCrear(BaseModel):
    nombre: str
    carpeta_padre_id: int | None = None


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


class UsuarioResueltoOut(UsuarioPendienteOut):
    """Usuario ya aprobado/rechazado, con su rol y estado finales."""
    rol: str
    estado: str