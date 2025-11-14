import asyncpg
from dotenv import load_dotenv
from passlib.context import CryptContext
import logging
import pytest_asyncio
from app.services.folder_services import FolderServices
import pytest
from app.schemas.schemas import RegisterUser, FolderCreationBody
from app.services.user_services import UserServices
from app.services.auth_services import AuthServices
import os

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
testing_database = os.getenv("TESTING_DATABASE")

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

if not testing_database:
    raise ValueError("TESTING_DATABASE environment variable not set")


@pytest_asyncio.fixture(scope="session")
async def db_pool():
    """Created once per session"""
    pool = await asyncpg.create_pool(testing_database)
    logger.info("Database pool created")
    yield pool
    await pool.close()
    logger.info("Database connection closed")


@pytest_asyncio.fixture(autouse=True)
async def clean_db(db_pool):
    """Runs before each test"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE users, files, folders, shares, permissions CASCADE"
        )
    yield


@pytest.fixture
def valid_user_data():
    return RegisterUser(
        username="test_user", email="test@test.com", password="test_password"
    )


@pytest.fixture(scope="session")
async def auth_services():
    """Created once per session"""
    auth_services = AuthServices(
        secret_key, algorithm, access_token_expire_minutes, pwd_context
    )
    return auth_services


@pytest.fixture
def valid_folder_data_no_parent():
    return FolderCreationBody(
        folder_name="test_folder",
    )


@pytest.fixture(scope="session")
async def user_services(db_pool, auth_services):
    """Created once per session"""
    return UserServices(db_pool, auth_services)


@pytest.fixture(scope="session")
async def folder_services(db_pool):
    """Created once per session"""
    return FolderServices(db_pool)
