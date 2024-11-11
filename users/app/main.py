import sys
sys.path.append("..")

import httpx
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator
from fastapi import Depends, FastAPI, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app import config
from shared.models.user import User, CreateUser, PublicUser,  UpdateUser
from app.operations import (
    get_current_active_user,
    authenticate_user,
    create_token,
    get_user_list,
)
import json
from aiohttp import ClientSession, TCPConnector

oauth2_authentication = OAuth2PasswordBearer(tokenUrl="token")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print("starting lifespan process")
    # The line `config.client_session = ClientSession(connector=TCPConnector(limit=100))` is creating
    # an instance of `ClientSession` with a `TCPConnector` that has a limit of 100 connections. This
    # is used to manage connections to external services. The `limit=100` parameter sets the maximum number of simultaneous
    # connections that can be made using this `ClientSession`. This helps in controlling the number of
    # connections and managing resources efficiently when interacting with external services.
    config.client_session = ClientSession(connector=TCPConnector(limit=100))
    yield
    await config.client_session.close()


app = FastAPI(lifespan=lifespan, title="Hello World API with DB")

router = APIRouter(
    prefix="/users",
    tags=["users"],
    # dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}},
)

# A base client to communicate with db_service
async def forward_request_to_db_service(endpoint: str, data: dict):
    async with httpx.AsyncClient() as client:
        print(f"{config.DB_API_BASE_PATH}/{endpoint}")
        response = await client.post(f"{config.DB_API_BASE_PATH}/{endpoint}", json=data)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()



@app.post("/create")
async def create_user(user_create: CreateUser):
    try:
        message = {
            "request_id": user_create.guid,
            "operation": "create",
            "entity": "user",
            "data": user_create.dict(),
        }

        # Forward the request to the db_service
        return await forward_request_to_db_service("users/operation", message)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error occurred while creating user: {str(e)}")


@app.put("/update/{user_guid_id}")
async def update_user(user_guid_id: str, user_update: UpdateUser):
    try:
        # Get user data to send to the db service
        user_data = user_update.dict(exclude_unset=True)

        data = {
            "request_id": user_guid_id,
            "operation": "update",
            "entity": "user",
            "data": user_data,
        }

        # Forward the request to the db_service
        return await forward_request_to_db_service("users/operation", data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error occurred while updating user: {str(e)}")


@app.delete("/delete/{user_guid_id}")
async def delete_user(user_guid_id: str):
    try:
        data = {
            "request_id": user_guid_id,
            "operation": "delete",
            "entity": "user",
            "data": {},
        }

        # Forward the request to the db_service
        return await forward_request_to_db_service("users/operation", data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error occurred while deleting user: {str(e)}")

# =======================default routes==========================
@app.get("/user")
async def root():
    return {"message": "Hello World"}


@app.post("/user/authentication")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    
    """this function is calling from operations file. this is authenticating the user calling user login end-point from db-service"""
    user: PublicUser = await authenticate_user(form_data.username, form_data.password)
    user = PublicUser.model_validate(user)

    """calling authentication microservice to generate the token for existing user"""
    token = await create_token(user)
    return token


"""
- Endpoint to create a new user in the system
- produce data to kafka topic, this topic is consumed by db-service
- db-service will produce response to kafka topic, this topic is consumed back by this api
- consumed response will be sent back to the user
"""
