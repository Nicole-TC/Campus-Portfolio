"""Errores de la API en JSON {error, codigo, mensaje}. Sin traceback al cliente."""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorAPI(Exception):
    def __init__(self, mensaje: str, codigo: int = 500) -> None:
        self.mensaje = mensaje
        self.codigo = codigo
        super().__init__(mensaje)


class ErrorValidacion(ErrorAPI):
    def __init__(self, mensaje: str = "Los datos enviados no son válidos") -> None:
        super().__init__(mensaje, 400)


class ErrorNoAutorizado(ErrorAPI):
    def __init__(self, mensaje: str = "Token ausente o inválido") -> None:
        super().__init__(mensaje, 401)


class ErrorProhibido(ErrorAPI):
    def __init__(self, mensaje: str = "No tenés permisos para esta acción") -> None:
        super().__init__(mensaje, 403)


class ErrorNoEncontrado(ErrorAPI):
    def __init__(self, mensaje: str = "No se encontró el recurso") -> None:
        super().__init__(mensaje, 404)


class ErrorCuota(ErrorAPI):
    def __init__(self, mensaje: str = "Cuota de almacenamiento agotada") -> None:
        super().__init__(mensaje, 413)


def armar_respuesta_error(codigo: int, mensaje: str) -> JSONResponse:
    return JSONResponse(
        status_code=codigo,
        content={
            "error": True,
            "codigo": codigo,
            "mensaje": mensaje,
        },
    )


def _mensaje_desde_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        primer_error = detail[0]
        if isinstance(primer_error, dict):
            return str(primer_error.get("msg", "Los datos enviados no son válidos"))
        return str(primer_error)
    if isinstance(detail, dict):
        return str(detail.get("mensaje") or detail.get("detail") or "Ocurrió un error")
    return "Ocurrió un error"


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorAPI)
    async def manejar_error_api(_request: Request, exc: ErrorAPI) -> JSONResponse:
        return armar_respuesta_error(exc.codigo, exc.mensaje)

    @app.exception_handler(SQLAlchemyError)
    async def manejar_error_bd(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Error de base de datos: %s", exc, exc_info=True)
        return armar_respuesta_error(500, "Error de conexión con la base de datos")

    @app.exception_handler(StarletteHTTPException)
    async def manejar_http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return armar_respuesta_error(exc.status_code, _mensaje_desde_detail(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def manejar_validacion(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return armar_respuesta_error(400, _mensaje_desde_detail(exc.errors()))

    @app.exception_handler(Exception)
    async def manejar_error_inesperado(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error interno no controlado: %s", exc, exc_info=True)
        return armar_respuesta_error(500, "Error interno del servidor")
