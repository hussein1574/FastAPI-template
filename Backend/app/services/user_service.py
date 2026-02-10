from app.schemas.pagination import PaginationParams, PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.core.exceptions import ConflictException
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.core.security import get_password_hash
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, user_in: UserCreate) -> User:

        if await self.user_repo.get_by_email(user_in.email):
            logger.warning("Attempt to create user with existing email: %s", user_in.email)
            raise ConflictException(detail="Email already registered")
        
        if await self.user_repo.get_by_username(user_in.username):
            logger.warning("Attempt to create user with existing username: %s", user_in.username)
            raise ConflictException(detail="Username already taken")
        
        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.model_dump(exclude={"password"})
        user_model = User(**user_data, password_hash = hashed_password)
        try:
            created_user = await self.user_repo.create(user_model)
            logger.info("User created successfully: user_id=%s", created_user.id)
            return created_user
        except IntegrityError:
            logger.error("IntegrityError during user creation for email=%s or username=%s", user_in.email, user_in.username)
            raise ConflictException(detail="Email or Username already taken (Race Condition detected)")
        

    async def update_user(self, user:User, user_in: UserUpdate) -> User:
        update_data = user_in.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != user.email:
            if await self.user_repo.get_by_email(update_data["email"]):
                raise ConflictException(detail="Email already registered")

        if "username" in update_data and update_data["username"] != user.username:
            if await self.user_repo.get_by_username(update_data["username"]):
                raise ConflictException(detail="Username already taken")

        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            updated_user = await self.user_repo.update(user)
            logger.info("User updated: user_id=%s", updated_user.id)
            return updated_user
        except IntegrityError:
            logger.error("IntegrityError during user update for user_id=%s", user.id)
            raise ConflictException(detail="Email or Username already taken (Race Condition detected)")

    async def delete_user(self, user: User) -> None:
        await self.user_repo.delete(user)
        logger.info("User deleted: user_id=%s", user.id)


    async def list_users(self, params: PaginationParams) -> PaginatedResponse[UserResponse]:
        users, total = await self.user_repo.get_all(params.offset, params.size)
        return PaginatedResponse.create(items=users, total=total, params=params) 