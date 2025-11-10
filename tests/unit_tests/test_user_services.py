from app.services.user_services import UserServices
from fastapi.exceptions import HTTPException
from passlib.context import CryptContext
from app.services.auth_services import AuthServices
import os
from dotenv import load_dotenv
import pytest

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

@pytest.fixture(scope="session")
async def user_services(db_pool, auth_services):
    """Created once per session"""
    return UserServices(db_pool, auth_services)

@pytest.fixture(scope="session")
async def auth_services():
    """Created once per session"""
    auth_services = AuthServices(secret_key, algorithm, access_token_expire_minutes, pwd_context)
    return auth_services

async def test_registering_duplicate_username_raises_409(user_services, valid_user_data):
    await user_services.register_new_user(valid_user_data.username, valid_user_data.email, valid_user_data.password)

    with pytest.raises(HTTPException) as exc_info:
        await user_services.register_new_user(valid_user_data.username, "other@test.com", valid_user_data.password)

    assert exc_info.value.status_code == 409

async def test_registering_duplicate_email_raises_409(user_services, valid_user_data):
    await user_services.register_new_user(valid_user_data.username, valid_user_data.email, valid_user_data.password)

    with pytest.raises(HTTPException) as exc_info:
        await user_services.register_new_user("otheruser", valid_user_data.email, valid_user_data.password)

    assert exc_info.value.status_code == 409

