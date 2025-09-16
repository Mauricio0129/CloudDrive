import jwt
from schemas.schemas import RegisterUser, UserInDB
from startup import access_token_expire_minutes
from datetime import datetime, timedelta, timezone


class BasicServices:
    def __init__(self, db, pwd_context, secret_key, algorithm, access_token_expire_minutes):
        self.db = db
        self.pwd_context = pwd_context
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes

    def hash_password(self, password):
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    async def check_if_user_exist_registration(self, user: RegisterUser):
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", user.username, user.email)
            return bool(row)

    async def check_if_user_exist_login(self, identifier) -> None | UserInDB:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $1", identifier)
            if not row:
                return None
            return UserInDB(**row)

    def create_access_token(self, data: dict):
        expires = datetime.now(timezone.utc) + timedelta(minutes=access_token_expire_minutes)
        data.update({"exp": expires})
        encoded_jwt = jwt.encode(data, key=self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    async def register_user(self, user: RegisterUser):
        password = self.hash_password(user.password.get_secret_value())
        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3)", user.username, user.email, password)
            if row:
                return True
            return False