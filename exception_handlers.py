from asyncpg.exceptions import PostgresError
from fastapi.responses import JSONResponse
from fastapi import Request

def adds_basic_services_global_handlers(app):
    @app.exception_handler(PostgresError)
    async def postgres_exception_handler(request: Request, exc: PostgresError):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )