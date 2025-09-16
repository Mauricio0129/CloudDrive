from contextlib import asynccontextmanager
from services.basic_services import BasicServices
from routes.user_routes import create_user_routes
from startup import DATABASE_URL, pwd_context, secret_key, algorithm, access_token_expire_minutes
import asyncpg

@asynccontextmanager
async def lifespan(app):
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("Database pool created")

    services = BasicServices(pool, pwd_context, secret_key, algorithm, access_token_expire_minutes)
    user_routes = create_user_routes(services)
    app.include_router(user_routes)
    yield

    await pool.close()
    print("Database pool closed")