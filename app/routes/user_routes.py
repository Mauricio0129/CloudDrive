from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from pygments.lexers import q

from app.schemas.schemas import (
    RegisterUser,
    UploadFileInfo,
    FolderCreationBody,
    FolderContents,
    FolderContentQuery,
    UpdateFolderName,
    RenameFile,
    Share,
    SharedWithMeResponse,
)
from fastapi.security import OAuth2PasswordRequestForm
from app.dependencies import get_token_and_decode
from fastapi.responses import JSONResponse


def create_user_routes(
    user_services,
    auth_services,
    folder_services,
    aws_services,
    file_services,
    share_services,
) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.get("/")
    async def root():
        return {
            "message": "Welcome to CloudDrive API",
            "status": "running",
            "version": "1.0.0"
        }

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
        user_id = await user_services.register_new_user(
            user.username, user.email, user.password
        )
        return JSONResponse(
            status_code=201, content={"message": "User successfully registered"}
        )

    @user_routes.post("/login")
    async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
        user = await user_services.get_user_id_and_password(form_data.username)
        if not auth_services.verify_password(form_data.password, user["password"]):
            raise HTTPException(status_code=401, detail="Incorrect Credentials")
        return {
            "access_token": auth_services.create_access_token(data={"sub": user["id"]}),
            "token_type": "bearer",
        }

    @user_routes.post("/drive")
    async def create_folder(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        folder_info: FolderCreationBody,
    ):
        folder_name = await folder_services.register_folder(
            folder_info.folder_name, folder_info.parent_folder_id, user_id
        )
        return {"message": f"Folder: {folder_name} successfully created"}

    @user_routes.get("/drive", response_model=FolderContents)
    async def get_root_folders(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        query: Annotated[FolderContentQuery, Query()],
    ):

        data = await folder_services.retrieve_folder_content(
            user_id, query.sort_by, query.order
        )
        return data

    @user_routes.get("/drive/{folder_id}", response_model=FolderContents)
    async def get_folder_content(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        query: Annotated[FolderContentQuery, Query()],
        folder_id: str,
    ):

        data = await folder_services.retrieve_folder_content(
            user_id, query.sort_by, query.order, folder_id
        )
        return data

    @user_routes.patch("/drive/{folder_id}")
    async def update_folder_name(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        folder_id: str,
        folder_info: UpdateFolderName,
    ):
        return await folder_services.rename_folder(
            user_id, folder_info.parent_folder_id, folder_id, folder_info.new_name
        )

    @user_routes.post("/file")
    async def upload_file(
        user_id: Annotated[str, Depends(get_token_and_decode)], file: UploadFileInfo
    ):
        if not file.file_conflict:
            return await file_services.upload_an_new_file(file, user_id)
        if file.file_conflict == "Replace":
            return await file_services.replace_existing_file(file, user_id)
        return await file_services.keep_both_files(file, user_id)

    @user_routes.get("/file/{file_id}")
    async def get_file(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        file_id: Annotated[str, Path(min_length=36, max_length=36)],
    ):
        return await file_services.get_user_presigned_download_url(user_id, file_id)

    @user_routes.patch("/file/{file_id}")
    async def rename_file(
        user_id: Annotated[str, Depends(get_token_and_decode)],
        file_id: Annotated[str, Path(min_length=36, max_length=36)],
        rename_info: RenameFile,
    ):
        return await file_services.rename_file(
            user_id, file_id, rename_info.file_name, rename_info.folder_id
        )

    @user_routes.post("/share")
    async def share(
        user_id: Annotated[str, Depends(get_token_and_decode)], share_info: Share
    ):
        if share_info.share_object_type == "file":
            return await share_services.share_file(user_id, share_info)
        return await share_services.share_folder(user_id, share_info)

    @user_routes.get("/shared-with-me", response_model=SharedWithMeResponse)
    async def share_with_me(user_id: Annotated[str, Depends(get_token_and_decode)]):
        return await share_services.get_shared_with_me(user_id)

    @user_routes.post("/profile_photo")
    async def upload_profile_image(
        user_id: Annotated[str, Depends(get_token_and_decode)], photo_size_in_bytes: int
    ):
        return aws_services.generate_presigned_photo_upload_url(
            user_id, photo_size_in_bytes
        )

    @user_routes.get("/profile_photo")
    async def get_profile_image(user_id: Annotated[str, Depends(get_token_and_decode)]):
        return aws_services.generate_presigned_photo_download_url(user_id)

    @user_routes.get("/health")
    def health_check():
        return {"status": "healthy"}

    return user_routes
