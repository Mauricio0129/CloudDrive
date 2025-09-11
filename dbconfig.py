from contextlib import asynccontextmanager
from dotenv import load_dotenv
from services.basic_services import BasicServices
from routes.user_routes import create_user_routes
import asyncpg
import os

load_dotenv()

env_vars = ["DATABASE", "USER", "DATABASE_PASSWORD", "HOST", "PORT",]

missing = [var for var in env_vars if not os.getenv(var)]
if missing:
    raise ValueError(f"Missing env vars: {', '.join(missing)}")

database = os.getenv("DATABASE")
user = os.getenv("USER")
password = os.getenv("DATABASE_PASSWORD")
host = os.getenv("HOST")
port = os.getenv("PORT")

DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{database}"

@asynccontextmanager
async def lifespan(app):
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("Database pool created")

    services = BasicServices(pool)
    user_routes = create_user_routes(services)
    app.include_router(user_routes)
    yield

    await pool.close()
    print("Database pool closed")