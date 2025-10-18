from typing import Annotated,Literal
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Header, Query
from app.schemas.schemas import RegisterUser, UploadHeaders, FolderCreationBody, FolderContents, FolderContentQuery
from fastapi.security import OAuth2PasswordRequestForm
from app.dependencies import get_token_and_decode
from fastapi.responses import JSONResponse


def create_user_routes(user_services, auth_services, storage_services, aws_services) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
        await user_services.check_if_user_exist_registration(user.username, user.email)
        hashed_password = auth_services.hash_password(user.password.get_secret_value())
        await user_services.register_user(user.username, user.email, hashed_password)
        return JSONResponse(status_code=201, content={"message": "User successfully registered"})

    @user_routes.post("/login")
    async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        user = await user_services.get_user_id_password(form_data.username)
        if not auth_services.verify_password(form_data.password, user["password"]):
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        return {
            "access_token": auth_services.create_access_token(data={"sub": user["id"]}),
            "token_type": "bearer"
        }

    @user_routes.post("/upload")
    async def upload_file(user_id: Annotated[str, Depends(get_token_and_decode)], file : UploadFile,
            upload_headers: Annotated[UploadHeaders, Header()]):
        stored_file = await storage_services.register_file(file, user_id, upload_headers.x_folder_id)
        return {"message": f"File: {stored_file} successfully uploaded"}

    @user_routes.post("/folder")
    async def create_folder(user_id: Annotated[str, Depends(get_token_and_decode)], folder_info : FolderCreationBody):

        folder_name = await storage_services.register_folder(folder_info.folder_name,
                                                           folder_info.parent_folder_id, user_id)
        return {"message": f"Folder: {folder_name} successfully created"}

    @user_routes.get("/drive", response_model=FolderContents)
    async def get_root_content(user_id: Annotated[str, Depends(get_token_and_decode)],
                               query: Annotated[FolderContentQuery, Query()]):

        data = await storage_services.retrieve_folder_content(user_id, query.sort_by, query.order)
        return data

    @user_routes.post("/profile_photo")
    async def upload_profile_image(user_id: Annotated[str, Depends(get_token_and_decode)], photo_size_in_bytes: int):
        return aws_services.generate_presigned_photo_upload_url(user_id, photo_size_in_bytes)

    @user_routes.get("/profile_photo")
    async def get_profile_image(user_id: Annotated[str, Depends(get_token_and_decode)]):
        return aws_services.generate_presigned_photo_download_url(user_id)

    return user_routes
