from fastapi import APIRouter, HTTPException
from schemas.schemas import RegisterUser
from services.basic_services import BasicServices


def create_user_routes(services: BasicServices) -> APIRouter:
    user_routes = APIRouter()

    @user_routes.post("/user")
    async def create_user(user: RegisterUser):
       if not await services.check_if_user_exist(user):
           if await services.register_user(user):
               return {"message": "User successfully registered"}
           return HTTPException(status_code=500, detail="Internal Server Error")
       return {"message": "User already exists!"}

    return user_routes
