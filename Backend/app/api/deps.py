from typing import Annotated
from uuid import UUID
from fastapi import Depends
from app.core.exceptions import UnauthorizedException
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.repositories.token_repo import TokenRepository
from app.repositories.password_reset_repo import PasswordResetRepository
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.core.security import decode_access_token
from fastapi.security import OAuth2PasswordBearer

db_dependency = Annotated[AsyncSession, Depends(get_db)]
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_user_repo(db: db_dependency)-> UserRepository:
    return UserRepository(db)

user_dependency = Annotated[UserRepository, Depends(get_user_repo)]

async def get_user_service(user_repo: user_dependency) -> UserService:
    return UserService(user_repo)


async def get_token_repo(db: db_dependency) -> TokenRepository:
    return TokenRepository(db)

token_dependency = Annotated[TokenRepository, Depends(get_token_repo)]

async def get_auth_service(user_repo: user_dependency, token_repo: token_dependency) -> AuthService:
    return AuthService(user_repo, token_repo)


async def get_password_reset_repo(db: db_dependency) -> PasswordResetRepository:
    return PasswordResetRepository(db)

password_reset_dependency = Annotated[PasswordResetRepository, Depends(get_password_reset_repo)]

async def get_password_reset_service(
    user_repo: user_dependency,
    password_reset_repo: password_reset_dependency,
    token_repo: token_dependency,
) -> PasswordResetService:
    return PasswordResetService(user_repo, password_reset_repo, token_repo)


async def get_current_user(token: Annotated[str, Depends(reusable_oauth2)], user_repo: user_dependency):
    payload = decode_access_token(token)
    subject = payload.sub
    if not subject:
        raise UnauthorizedException(detail="Unauthorized User")
    try:
        user_id = UUID(subject)
    except ValueError:
        raise UnauthorizedException(detail="Unauthorized User")
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedException(detail="Unauthorized User")
    return user


