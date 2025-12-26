from dotenv import load_dotenv
from passlib.context import CryptContext
import os
import json
import boto3
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

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
    "REGION",
]


## Helper function to corroborate the env vars exist
def verify_presence_of_all_env_vars(source=None):
    if source:
        missing = [var for var in env_vars if not source.get(var)]
    else:  ## in both parts we make sure to use collection methods that don't raise exceptions on its own
        missing = [var for var in env_vars if not os.getenv(var)]

    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")


## Verify if we are inside production environment
if os.getenv("ENVIRONMENT") == "production":
    ## If true then collect env from aws secret manager, and we load the resulting json response
    client = boto3.client("secretsmanager", region_name="us-east-1")
    cache_config = SecretCacheConfig()
    cache = SecretCache(config=cache_config, client=client)
    secrets_json = cache.get_secret_string("CloudDriveEnvVars")
    env_creds = json.loads(secrets_json)

    ## Integrity verification step
    verify_presence_of_all_env_vars(env_creds)

    database = env_creds["DATABASE"]
    db_user = env_creds["DB_USER"]
    password = env_creds["DATABASE_PASSWORD"]
    host = env_creds["HOST"]
    port = env_creds["PORT"]
    secret_key = env_creds["SECRET_KEY"]
    algorithm = env_creds["ALGORITHM"]
    access_token_expire_minutes = int(env_creds["ACCESS_TOKEN_EXPIRE_MINUTES"])
    bucket_name = env_creds["BUCKET_NAME"]
    region = env_creds["REGION"]
    os.environ["LAMBDA_SECRET"] = env_creds["LAMBDA_SECRET"]

else:
    ## Integrity verification step
    verify_presence_of_all_env_vars()

    database = os.getenv("DATABASE")
    db_user = os.getenv("DB_USER")  # renamed for clarity
    password = os.getenv("DATABASE_PASSWORD")
    host = os.getenv("HOST")
    port = os.getenv("PORT")
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM")
    access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    bucket_name = os.getenv("BUCKET_NAME")
    region = os.getenv("REGION")


DATABASE_URL = f"postgresql://{db_user}:{password}@{host}:{port}/{database}"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
