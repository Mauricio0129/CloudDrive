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
    x_folder_id: Annotated[Optional[str], Field(min_length=3, max_length=36)] = None
    x_file_folder_conflict: Optional[Literal["Replace", "Keep"]] = None

