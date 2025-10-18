from ..schemas.schemas import UserInDB
from fastapi import HTTPException

# noinspection SqlNoDataSourceInspection
class UserServices:

    def __init__(self, db):
        self.db = db

##At registration we must check neither the username , email are in use
    async def check_if_user_exist_registration(self, username, email) -> None:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", username, email)
            if row:
                raise HTTPException(status_code=409, detail="User already exists")

##Here we use the identifier for both fields as the user could use either email or username to login
    async def get_user_id_password(self, identifier) -> dict:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT id, password FROM users WHERE username = $1 OR email = $1", identifier)
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_data = dict(row)
            user_data["id"] = str(user_data["id"])  ##we convert the uuid object to a string
            return user_data

    async def register_user(self, username, email,  hashed_password) -> str:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3) RETURNING id",
                                      username, email, hashed_password)
            return str(row["id"])