import asyncio
from datetime import datetime, timezone
from sqlalchemy import delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.token import RefreshToken
from app.models.password_reset import PasswordResetToken
import logging

logger = logging.getLogger(__name__)

async def cleanup_expired_tokens(session: AsyncSession):
    async with session.begin():
        stmt = delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < datetime.now(timezone.utc),
                RefreshToken.revoked == True
            )
        )
        result = await session.execute(stmt)
        
        # Clean up expired/used password reset tokens
        reset_stmt = delete(PasswordResetToken).where(
            or_(
                PasswordResetToken.expires_at < datetime.now(timezone.utc),
                PasswordResetToken.used == True
            )
        )
        reset_result = await session.execute(reset_stmt)
        await session.commit()
        logger.info("Cleaned up %d expired/used password reset tokens", reset_result.rowcount)
        logger.info("Cleaned up %d expired/revoked refresh tokens", result.rowcount)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_expired_tokens())