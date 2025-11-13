from contextlib import asynccontextmanager
from .startup import DATABASE_URL, pwd_context, secret_key, algorithm, access_token_expire_minutes
from .services.user_services import UserServices
from .services.auth_services import AuthServices
from .services.folder_services import FolderServices
from .services.file_services import FileServices
from .services.aws import AwsServices
from .routes.user_routes import create_user_routes
import asyncpg
import logging

# Module-level logger
logger = logging.getLogger(__name__)

# Basic logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

@asynccontextmanager
async def lifespan(app):
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Database pool created")
    except Exception as exc:
        logger.error(f"Failed to create database pool: {exc}")
        raise

    auth_services = AuthServices(secret_key, algorithm, access_token_expire_minutes, pwd_context)
    user_services = UserServices(pool, auth_services)
    folder_services = FolderServices(pool)
    file_services = FileServices(pool, folder_services)

    user_routes = create_user_routes(user_services, auth_services, folder_services, AwsServices, file_services)
    app.include_router(user_routes)

    yield
    try:
        await pool.close()
        logger.info("Database connection closed")
    except Exception as exc:
        logger.error(f"Error closing the database pool: {exc}")