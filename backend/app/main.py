"""
Punto de arranque de la API CampusCloud.

Esto es solo el esqueleto para confirmar que el contenedor levanta bien.
El desarrollo real (modelos, autenticación, endpoints de archivos, etc.)
lo arma el equipo a partir de acá.
¿Cómo agregar nuevos módulos y endpoints al proyecto?
--------------------------------------------------------
Buenas prácticas: NO escribir todos los endpoints dentro de este archivo main.py.
El desarrollo debe ser modular mediante 'APIRouter':
Paso 1: Crear un archivo para el módulo dentro de 'app/routers/'
        (ej: app/routers/auth.py o app/routers/archivos.py).
Paso 2: Definir el router dentro de ese archivo:
        ---------------------------------------------------------
        from fastapi import APIRouter
        
        router = APIRouter(prefix="/archivos", tags=["Archivos"])
        @router.get("/")
        def listar_archivos():
            return {"archivos": []}
        ---------------------------------------------------------
Paso 3: "Enchufar" o incluir el router aquí en main.py con UNA sola línea:
        ---------------------------------------------------------
        from app.routers import auth, archivos
        app.include_router(auth.router)
        app.include_router(archivos.router)
        ---------------------------------------------------------
Al incluirlo aquí:
  - El frontend podrá consumirlo automáticamente bajo '/api/archivos/'.
  - Aparecerá documentado y listo para probar en la interfaz web de Swagger (/api/docs).
3. Sugerencia de estructura recomendada para el equipo:
-------------------------------------------------------
  app/config.py        -> Lectura dinámica de variables de entorno (.env).
  app/database.py      -> Conexión a PostgreSQL (engine, SessionLocal, get_db).
  app/models.py        -> Modelos de base de datos (tablas: Usuario, Archivo, etc.).
  app/schemas.py       -> Validaciones de entrada/salida de datos con Pydantic.
  app/dependencies.py  -> Dependencias de seguridad (validar JWT, permisos de admin).
  app/routers/         -> Endpoints separados por módulo (auth, archivos, admin).
  app/services/        -> Lógica de negocio pesada (cálculo de cuotas, validaciones).

"""
from logging import root
from fastapi import FastAPI
from app.database import verificar_conexion
from app.excepciones import registrar_manejadores
from app.routers import telegram

app = FastAPI(
    title="CampusCloud API",
    description="Almacenamiento privado, cuotas y gestión de recursos para el instituto.",
    version="0.1.0",
    root_path="/api",
)
registrar_manejadores(app)

app.include_router(telegram.router)


@app.get("/salud")
def salud():
    """Endpoint de prueba: verifica el estado del backend y la conexión con PostgreSQL."""
    db_conectada = verificar_conexion()
    return {
        "status": "ok" if db_conectada else "degradado",
        "backend": "funcionando",
        "database": "conectada" if db_conectada else "error_de_conexion"
    }
