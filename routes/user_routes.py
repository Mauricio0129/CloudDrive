from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Header
from schemas.schemas import RegisterUser, UploadHeaders
from fastapi.security import OAuth2PasswordRequestForm
from dependencies import get_token_and_decode


def create_user_routes(user_services, auth_services, storage_services) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
       if not await user_services.check_if_user_exist_registration(user.username, user.email):
           password = auth_services.hash_password(user.password.get_secret_value())
           if await user_services.register_user(user.username, user.email, password):
               return {"message": "User successfully registered"}
           raise HTTPException(status_code=500, detail="Internal Server Error")
       return {"message": "User already exists!"}

    @user_routes.post("/login")
    async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        user = await user_services.get_user(form_data.username)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        if not auth_services.verify_password(form_data.password, user.password):
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        return {
            "access_token": auth_services.create_access_token(data={"sub": user.id}),
            "token_type": "bearer"
        }

    @user_routes.post("/upload")
    async def upload_file(user: Annotated[str, Depends(get_token_and_decode)], file : UploadFile,
            upload_headers: Annotated[UploadHeaders, Header()]):
        await storage_services.register_file(file, user, upload_headers.x_folder_id)
        return {"message": "File successfully uploaded"}

    return user_routes
