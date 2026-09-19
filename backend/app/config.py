from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Variables obligatorias (SIN hardcodeo: si no están en el .env, la app no arranca)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    JWT_SECRET: str

    # El nombre de la base de datos puede venir como DB_NAMEDB o DB_NAME
    DB_NAMEDB: Optional[str] = None
    DB_NAME: Optional[str] = None

    # Parámetros técnicos del protocolo JWT
    JWT_ALGORITHM: str = "HS256"  # Nombre del algoritmo estándar (no es sensible)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # Duración del token: 24 horas

    # Variables opcionales que vienen del .env
    PUBLIC_PORT: Optional[int] = None
    TELEGRAM_TOKEN: Optional[str] = None

    # Configuración para leer el archivo .env de la raíz
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_name(self) -> str:
        """Obtiene el nombre de la BD desde DB_NAMEDB o DB_NAME."""
        nombre = self.DB_NAMEDB or self.DB_NAME
        if not nombre:
            raise ValueError("Debes definir DB_NAMEDB o DB_NAME en tu archivo .env")
        return nombre

    @property
    def database_url(self) -> str:
        """Construye la URL de conexión a PostgreSQL dinámicamente en tiempo de ejecución."""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.database_name}"
        )


settings = Settings()

