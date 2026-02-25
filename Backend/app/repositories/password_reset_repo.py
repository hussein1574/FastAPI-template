from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_token
from app.models.password_reset import PasswordResetToken


class PasswordResetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token

    async def get_by_token(self, token: str) -> PasswordResetToken | None:
        query = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def mark_used(self, reset_token: PasswordResetToken) -> None:
        reset_token.used = True
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used == False,
            )
            .values(used=True)
        )
        await self.db.execute(stmt)
        await self.db.flush()
