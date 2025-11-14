from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
from .startup import secret_key, algorithm
from typing import Annotated
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_token_and_decode(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except jwt.PyJWTError:
        raise credentials_exception
