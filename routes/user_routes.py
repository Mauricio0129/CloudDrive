from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends
from schemas.schemas import RegisterUser
from services.basic_services import BasicServices
from fastapi.security import OAuth2PasswordRequestForm


def create_user_routes(services: BasicServices) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
       if not await services.check_if_user_exist_registration(user):
           if await services.register_user(user):
               return {"message": "User successfully registered"}
           return HTTPException(status_code=500, detail="Internal Server Error")
       return {"message": "User already exists!"}

    @user_routes.post("/login")
    async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        user = await services.check_if_user_exist_login(form_data.username)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        if not services.verify_password(form_data.password, user.password):
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        return {
            "access_token": services.create_access_token(data={"sub": user.username}),
            "token_type": "bearer"
        }

    return user_routes
