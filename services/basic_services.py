from typing import Annotated
from fastapi import Depends, HTTPException, UploadFile
from startup import oauth2_scheme
import jwt
from schemas.schemas import RegisterUser, UserInDB
from datetime import datetime, timedelta, timezone
from asyncpg.exceptions import PostgresError


# noinspection SqlNoDataSourceInspection
class BasicServices:
    def __init__(self, db, pwd_context, secret_key, algorithm, access_token_expire_minutes):
        self.db = db
        self.pwd_context = pwd_context
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.oauth2_scheme3 = oauth2_scheme

    def hash_password(self, password) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    async def check_if_user_exist_registration(self, user: RegisterUser) -> bool:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $2", user.username, user.email)
            return bool(row)

    async def get_user(self, identifier) -> None | UserInDB:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 OR email = $1", identifier)
            if not row:
                return None
            user_data = dict(row)
            user_data["id"] = str(user_data["id"])
            return UserInDB(**user_data)

    def create_access_token(self, data: dict) -> str:
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        data.update({"exp": expires})
        encoded_jwt = jwt.encode(data, key=self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    async def register_user(self, user: RegisterUser) -> bool:
        password = self.hash_password(user.password.get_secret_value())
        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO users (username, email, password) "
                                      "VALUES ($1, $2, $3)", user.username, user.email, password)
            return bool(row)

    ## oauth2_scheme cant be passed in the way of dependency injection
    ## fastapi can resolve for dependency tree without object that contains the dependency itself as attr
    async def get_token_and_decode(self, token: Annotated[str, Depends(oauth2_scheme)]) -> str:
        credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials",
                                              headers={"WWW-Authenticate": "Bearer"},)
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            if user_id is None:
                raise credentials_exception
            return user_id
        except jwt.PyJWTError:
            raise credentials_exception

    async def check_if_file_exist_for_user_at_location(self, user_id, folder_id, file_name) -> str:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("SELECT name FROM files WHERE owner_id = $1 AND folder_id = $2 AND name = $3"
                                      , user_id, folder_id, file_name)
            return str(row)

    @staticmethod
    async def calculate_file_size(file: UploadFile) -> int:
        size = 0
        read_size = 1048576
        while True:
            chunk = await file.read(read_size)
            if not chunk:
                break
            size += len(chunk)
        return size

    @staticmethod
    def format_file_size(size: int) -> str:
        if size >= 1000000:
            size = size // 1000000
            size = str(size) + "MB"
        elif size >= 1000:
            size = size // 1000
            size = str(size) + "KB"
        else:
            size = str(size) + "B"
        return size

    async def register_file(self, file:UploadFile, user_id, folder_id) -> bool:
        size = await self.calculate_file_size(file)              ## calculate file size asynchronously
        name, ext = file.filename.rsplit(".", 1)    ## split filename into name and extension
        size = self.format_file_size(size)                      ## format file size(e.g, bytes to KB, MB)

        async with self.db.acquire() as conn:
            row = await conn.execute("INSERT INTO files (name, size, type, owner_id, folder_id) "
                                        "VALUES ($1, $2, $3, $4, $5)", name, size, ext, user_id, folder_id)
        return bool(row)
