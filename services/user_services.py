from schemas.schemas import UserInDB

class UserServices:

    def __init__(self, db):
        self.db = db

    async def check_if_user_exist_registration(self, username, email) -> bool:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", username, email)
            return bool(row)

    async def get_user(self, identifier) -> None | UserInDB:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $1", identifier)
            if not row:
                return None
            user_data = dict(row)
            user_data["id"] = str(user_data["id"])
            return UserInDB(**user_data)

    async def register_user(self, username, email,  hashed_password) -> bool:
        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3)", username, email, hashed_password)
            return bool(row)