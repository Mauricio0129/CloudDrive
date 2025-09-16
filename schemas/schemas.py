from pydantic import BaseModel, Field, EmailStr, SecretStr

class RegisterUser(BaseModel):
    username: str = Field(min_length=3, max_length=15)
    email: EmailStr = Field(min_length=3, max_length=35)
    password: SecretStr = Field(min_length=3, max_length=20)

class UserInDB(BaseModel):
    username: str = Field(min_length=3, max_length=15)
    email: EmailStr = Field(min_length=3, max_length=35)
    password: str = Field(min_length=3, max_length=70)