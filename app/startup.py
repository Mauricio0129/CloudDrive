from dotenv import load_dotenv
from passlib.context import CryptContext
import os

load_dotenv()

# Required environment variables
env_vars = [
    "DATABASE",
    "DB_USER",
    "DATABASE_PASSWORD",
    "HOST",
    "PORT",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "BUCKET_NAME",
]

missing = [var for var in env_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing env vars: {', '.join(missing)}")

database = os.getenv("DATABASE")
db_user = os.getenv("DB_USER")  # renamed for clarity
password = os.getenv("DATABASE_PASSWORD")
host = os.getenv("HOST")
port = os.getenv("PORT")
secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
bucket_name = os.getenv("BUCKET_NAME")

DATABASE_URL = f"postgresql://{db_user}:{password}@{host}:{port}/{database}"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
