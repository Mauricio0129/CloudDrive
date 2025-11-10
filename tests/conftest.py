import os
import asyncpg
from dotenv import load_dotenv
import logging
import pytest_asyncio
import pytest
from app.schemas.schemas import RegisterUser

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

load_dotenv()
testing_database = os.getenv("TESTING_DATABASE")

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
        await conn.execute("TRUNCATE users, files, folders, shares, permissions CASCADE")
    yield

@pytest.fixture
def valid_user_data():
    return RegisterUser(
        username="testuser",
        email="test@test.com",
        password="testpassword"
    )