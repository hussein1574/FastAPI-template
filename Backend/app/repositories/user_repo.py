from sqlalchemy import select, or_, func
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self , user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def update(self, user: User) -> User:
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()
        
    async def get_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_id(self, id: int) -> User | None:
        query = select(User).where(User.id == int(id))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, identifier: str) -> User | None:
        query = select(User).where(
            or_(User.email == identifier, User.username == identifier)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(self, offset: int, limit: int) -> tuple[list[User], int]:
        count_query = select(func.count()).select_from(User)
        total = (await self.db.execute(count_query)).scalar()

        query = select(User).offset(offset).limit(limit).order_by(User.id)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total
