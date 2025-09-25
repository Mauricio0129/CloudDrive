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

class FolderContent(BaseModel):
    id: str
    name: str
    size: Optional[str] = None
    type: Optional[str] = None # only for files allow us to differentiate between a file and a folder
    last_interaction: str # Convert datetime to string
    parent_folder_id: Optional[str] = None
    # useful for going back process a user can go back and the frontend only needs to request
    # the parent folder which is the same as going back
