from asyncpg.exceptions import PostgresError
from fastapi.responses import JSONResponse
from fastapi import Request, HTTPException
import logging

logger = logging.getLogger(__name__)


def adds_basic_services_global_handlers(app):
    @app.exception_handler(PostgresError)
    async def postgres_exception_handler(request: Request, exc: PostgresError):
        # CHANGE 1: Add exc_info=True to get full stack trace
        # CHANGE 2: Include request details (method + path) to know which endpoint failed
        logger.error(
            f"Database error - {request.method} {request.url.path}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )

    @app.exception_handler(Exception)
    async def catch_all_exception_handler(request: Request, exc: Exception):
        # Don't catch HTTPExceptions (business logic) - let FastAPI handle them
        if isinstance(exc, HTTPException):
            raise exc

        # This catches bugs in your code that aren't database-related
        logger.critical(
            f"Unexpected error - {request.method} {request.url.path}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )