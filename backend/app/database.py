import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, DeclarativeBase, Session
from app.config import settings

logger = logging.getLogger(__name__)

# Creación del engine de SQLAlchemy
# pool_pre_ping=True valida que la conexión remota a la VPS siga viva antes de usarla
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # Cambiar a True si se desea ver las sentencias SQL en consola
)

# Fábrica de sesiones de base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para definir modelos (SQLAlchemy 2.0)
class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia de FastAPI para inyectar la sesión de base de datos en los endpoints.
    Asegura que la sesión siempre se cierre al terminar la petición HTTP.
    
    Ejemplo de uso en un router:
        @router.get("/usuarios")
        def listar_usuarios(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verificar_conexion() -> bool:
    """Verifica si la base de datos remota está accesible ejecutando un SELECT 1."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Conexión a la base de datos exitosa.")
        return True
    except Exception as e:
        logger.error(f"❌ Error al conectar con la base de datos: {e}")
        return False
