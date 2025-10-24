from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Query
from app.schemas.schemas import (RegisterUser, UploadFileInfo, FolderCreationBody, FolderContents, FolderContentQuery,
                                 UpdateFolderName)
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

    @user_routes.post("/drive")
    async def create_folder(user_id: Annotated[str, Depends(get_token_and_decode)], folder_info : FolderCreationBody):

        folder_name = await storage_services.register_folder(folder_info.folder_name,
                                                           folder_info.parent_folder_id, user_id)
        return {"message": f"Folder: {folder_name} successfully created"}

    @user_routes.get("/drive", response_model=FolderContents)
    async def get_root_folders(user_id: Annotated[str, Depends(get_token_and_decode)],
                               query: Annotated[FolderContentQuery, Query()]):

        data = await storage_services.retrieve_folder_content(user_id, query.sort_by, query.order)
        return data

    @user_routes.get("/drive/{folder_id}", response_model=FolderContents)
    async def get_folder_content(user_id: Annotated[str, Depends(get_token_and_decode)],
                                 query: Annotated[FolderContentQuery, Query()], folder_id: str):

        data = await storage_services.retrieve_folder_content(user_id, query.sort_by, query.order, folder_id)
        return data

    @user_routes.patch("/drive/{folder_id}")
    async def update_folder_name(user_id: Annotated[str, Depends(get_token_and_decode)], folder_id: str,
                                 folder_info: UpdateFolderName):
        return await storage_services.rename_folder(user_id, folder_info.parent_folder_id, folder_id,
                                                    folder_info.new_name)

    @user_routes.post("/file")
    async def upload_file(user_id: Annotated[str, Depends(get_token_and_decode)], file:UploadFileInfo):
        return await storage_services.verify_file_and_generate_aws_presigned_upload_url(file, user_id)

    @user_routes.post("/profile_photo")
    async def upload_profile_image(user_id: Annotated[str, Depends(get_token_and_decode)], photo_size_in_bytes: int):
        return aws_services.generate_presigned_photo_upload_url(user_id, photo_size_in_bytes)

    @user_routes.get("/profile_photo")
    async def get_profile_image(user_id: Annotated[str, Depends(get_token_and_decode)]):
        return aws_services.generate_presigned_photo_download_url(user_id)

    return user_routes
