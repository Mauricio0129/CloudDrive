from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Header
from schemas.schemas import RegisterUser, UploadHeaders
from services.basic_services import BasicServices
from fastapi.security import OAuth2PasswordRequestForm


def create_user_routes(services: BasicServices) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
       if not await services.check_if_user_exist_registration(user):
           if await services.register_user(user):
               return {"message": "User successfully registered"}
           raise HTTPException(status_code=500, detail="Internal Server Error")
       return {"message": "User already exists!"}

    @user_routes.post("/login")
    async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        user = await services.get_user(form_data.username)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        if not services.verify_password(form_data.password, user.password):
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        return {
            "access_token": services.create_access_token(data={"sub": user.id}),
            "token_type": "bearer"
        }

    @user_routes.post("/upload")
    async def upload_file(user: Annotated[str, Depends(services.get_token_and_decode)], file : UploadFile,
            upload_headers: Annotated[UploadHeaders, Header()]):
        await services.register_file(file, user, upload_headers.x_folder_id)
        return {"message": "File successfully uploaded"}

    return user_routes
