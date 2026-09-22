"""Esquemas Pydantic de entrada/salida de la API."""
from typing import List

from pydantic import BaseModel


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