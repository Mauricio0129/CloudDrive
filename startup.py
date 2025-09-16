from dotenv import load_dotenv
from passlib.context import CryptContext
import os

load_dotenv()

## CHECKS THERES NO MISSING ENV VARIABLES
env_vars = ["DATABASE", "USER", "DATABASE_PASSWORD", "HOST", "PORT", "SECRET_KEY", "ALGORITHM",
            "ACCESS_TOKEN_EXPIRE_MINUTES"]

missing = [var for var in env_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing env vars: {', '.join(missing)}")

database = os.getenv("DATABASE")
user = os.getenv("USER")
password = os.getenv("DATABASE_PASSWORD")
host = os.getenv("HOST")
port = os.getenv("PORT")
secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{database}"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")