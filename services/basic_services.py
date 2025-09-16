from passlib.context import CryptContext
from schemas.schemas import RegisterUser


class BasicServices:
    def __init__(self, db, pwd_context):
        self.db = db
        self.pwd_context = pwd_context

    def hash_password(self, password):
        return self.pwd_context.hash(password)

    async def check_if_user_exist_registration(self, user: RegisterUser):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", user.username, user.email)
            return bool(row)

    async def register_user(self, user: RegisterUser):
        password = self.hash_password(user.password.get_secret_value())
        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3)", user.username, user.email, password)
            if row:
                return True
            return False