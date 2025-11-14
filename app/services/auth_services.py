from datetime import datetime, timedelta, timezone
import jwt


class AuthServices:
    def __init__(self, secret_key, algorithm, access_token_expire_minutes, pwd_context):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.pwd_context = pwd_context

    def hash_password(self, password) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict) -> str:
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=self.access_token_expire_minutes
        )
        data.update({"exp": expires})
        encoded_jwt = jwt.encode(data, key=self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
