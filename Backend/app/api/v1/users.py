from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.user_service import UserService
from app.api.deps import get_user_service, get_current_user
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.models.user import User

router = APIRouter()

user_service = Annotated[UserService, Depends(get_user_service)]

@router.post("/", response_model=UserResponse)
async def create_user(user_in: UserCreate, service: user_service) -> UserResponse:
    return await service.create_user(user_in)

@router.get("/me", response_model=UserResponse)
async def details(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: user_service,
):
    return await service.update_user(current_user, user_in)

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_user)],
    service: user_service,
):
    await service.delete_user(current_user)


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    service: user_service,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    return await service.list_users(PaginationParams(page=page, size=size))