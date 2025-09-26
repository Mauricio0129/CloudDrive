import uuid

from pydantic import BaseModel, Field, EmailStr, SecretStr
from typing import Literal, Annotated, Optional

class RegisterUser(BaseModel):
    username: str = Field(min_length=3, max_length=15)
    email: EmailStr = Field(min_length=3, max_length=40)
    password: SecretStr = Field(min_length=3, max_length=20)

## typical uuid length is 36 and 60 for hashed passwords hashed with bcrypt
class UserInDB(BaseModel):
    id: str = Field(min_length=3, max_length=36)
    username: str = Field(min_length=3, max_length=15)
    email: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=3, max_length=60)

## pydantic model used to validate header parameters for the upload route handler function
## both optional as files/folders can be at root which doesn't need folder_id
## and there can or cannot be a file/folder conflict
class UploadHeaders(BaseModel):
    x_folder_id: Annotated[Optional[str], Field(min_length=36, max_length=36)] = None
    x_file_folder_conflict: Optional[Literal["Replace", "Keep"]] = None

class FolderHeaders(BaseModel):
    x_parent_folder_id: Annotated[Optional[str], Field(min_length=36, max_length=36)] = None
    x_folder_name: str = Field(min_length=3, max_length=25)

class FileInfo(BaseModel):
    id: str
    name: str
    size: str
    type: str
    created_at: str
    last_interaction: str

class FolderInfo(BaseModel):
    id : str
    name: str
    created_at: str
    last_interaction: str
    parent_folder_id: Optional[str] = None

class UserInfo(BaseModel):
    username: str
    email: EmailStr
    available_storage_kb: int
    total_storage_kb: int

class MainDriveInfo(BaseModel):
    user: UserInfo
    files: list[FileInfo]
    folders: list[FolderInfo]