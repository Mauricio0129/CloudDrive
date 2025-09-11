from schemas.schemas import RegisterUser
from security import pwd_context


class BasicServices:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def hash_password(password):
        return pwd_context.hash(password)

    async def check_if_user_exist(self, user: RegisterUser):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", user.email)
            if not row:
                return False
            return True

    async def register_user(self, user: RegisterUser):
        password = self.hash_password(user.password.get_secret_value())
        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3)", user.username, user.email, password)
            if row:
                return True
            return False