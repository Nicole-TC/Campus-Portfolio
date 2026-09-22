"""
Modelos de base de datos (SQLAlchemy 2.0).

Reflejan las tablas definidas en bd-campuscloud.sql. Por ahora solo se
mapean las tablas que necesita el módulo Mi Perfil.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    cuota_total_mb: Mapped[int] = mapped_column(Integer)
    max_file_size_mb: Mapped[int] = mapped_column(Integer)


class Estado(Base):
    __tablename__ = "estados"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)


class Extension(Base):
    __tablename__ = "extensiones"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(15), unique=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    dni: Mapped[str] = mapped_column(String(15), unique=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True)
    id_rol: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    id_estado: Mapped[int] = mapped_column(ForeignKey("estados.id"))
    cuota_personalizada_mb: Mapped[Optional[int]] = mapped_column(Integer)
    max_file_personalizado_mb: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_registro: Mapped[datetime]

    rol: Mapped[Rol] = relationship()
    estado: Mapped[Estado] = relationship()


class RolExtensionBloqueada(Base):
    __tablename__ = "roles_extensiones_bloqueadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    extension_id: Mapped[int] = mapped_column(ForeignKey("extensiones.id"))


class UsuarioExtensionProhibida(Base):
    __tablename__ = "usuarios_extensiones_prohibidas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    extension_id: Mapped[int] = mapped_column(ForeignKey("extensiones.id"))


class Archivo(Base):
    __tablename__ = "archivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    carpeta_id: Mapped[Optional[int]] = mapped_column(Integer)
    id_extension: Mapped[int] = mapped_column(ForeignKey("extensiones.id"))
    nombre_disco: Mapped[str] = mapped_column(String(255))
    nombre_original: Mapped[str] = mapped_column(String(255))
    ruta: Mapped[str] = mapped_column(String(500))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    en_papelera: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_eliminacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_subida: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Permiso(Base):
    __tablename__ = "permisos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    archivo_id: Mapped[int] = mapped_column(
        ForeignKey("archivos.id")
    )

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id")
    )

    permiso: Mapped[Optional[str]] = mapped_column(String(20))

    fecha_compartido: Mapped[Optional[datetime]]
