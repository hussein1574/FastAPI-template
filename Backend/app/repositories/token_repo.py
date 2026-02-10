from sqlalchemy import select
from app.models.token import RefreshToken
from sqlalchemy.ext.asyncio import AsyncSession

class TokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token
    
    async def update(self, token:RefreshToken) -> RefreshToken:
        await self.db.flush()
        await self.db.refresh(token)
        return token
    
    async def get_by_token(self, token: str, for_update: bool = False) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.token == token)
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def revoke_token(self, token: str) -> bool:
        stored = await self.get_by_token(token, for_update=True)
        if stored:
            stored.revoked = True
            await self.db.flush()
            return True
        return False


    


