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


class ArchivoPapeleraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_original: str
    en_papelera: bool
    fecha_eliminacion: Optional[datetime]

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
