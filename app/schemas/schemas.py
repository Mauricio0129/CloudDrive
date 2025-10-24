from pydantic import BaseModel, Field, EmailStr, SecretStr, model_validator, ValidationError
from typing import Literal, Annotated, Optional
from ..helpers.file_utils import is_allowed_extension

class RegisterUser(BaseModel):
    """User registration request data."""
    username: str = Field(min_length=3, max_length=15)
    email: EmailStr = Field(min_length=3, max_length=40)
    password: SecretStr = Field(min_length=3, max_length=20)

class UserInDB(BaseModel):
    """
    User database model with hashed password.
    UUID v4 is 36 chars, bcrypt hashes are 60 chars.
    """
    id: str = Field(min_length=36, max_length=36)
    username: str = Field(min_length=3, max_length=15)
    email: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=3, max_length=60)

class UploadFileInfo(BaseModel):
    """
    Headers for file upload endpoint.
    folder_id: Optional, files can be uploaded to root.
    conflict: Optional, only needed when name collision detected.
    """
    file_name: str = Field(min_length=3, max_length=50)
    file_size_in_bytes: int
    folder_id: Annotated[Optional[str], Field(min_length=36, max_length=36)] = None
    file_conflict: Optional[Literal["Replace", "Keep"]] = None

    @model_validator(mode="after")
    def validate_extension(self):
        ext = is_allowed_extension(self.file_name)
        if ext is True:
            return self
        raise ValueError(f"Unsupported file extension: '{ext or '(none)'}'")

class FolderCreationBody(BaseModel):
    """
    Body for folder creation endpoint.
    parent_folder_id: Optional, folders can be created at root.
    """
    parent_folder_id: Annotated[Optional[str], Field(
        min_length=36,
        max_length=36,
        description= "Not required when making root level folders")] = None
    folder_name: str = Field(min_length=3, max_length=25)

class FolderOrFileInfo(BaseModel):
    id: str
    name: str
    size: Optional[str] = None
    type: Optional[str] = None
    created_at: str
    last_interaction: str
    parent_folder_id: Optional[str] = None

class UserInfo(BaseModel):
    """User account information including storage quota."""
    username: str
    email: EmailStr
    available_storage_in_bytes: int
    total_storage_in_bytes: int

class FolderContents(BaseModel):
    """
    Folder contents response. User info only included at root level (location=None).
    """
    user: Optional[UserInfo] = None  # Only present at root
    files_and_folders: list[FolderOrFileInfo]


class FolderContentQuery(BaseModel):
    sort_by : Literal["name", "created_at", "last_interaction"] = "last_interaction"
    order : Literal["DESC", "ASC"] = "ASC"


class UpdateFolderName(BaseModel):
    new_name: str = Field(min_length=1, max_length=25)
    parent_folder_id: Annotated[Optional[str], Field(min_length=36, max_length=36)] = None