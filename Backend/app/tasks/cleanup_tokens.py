import asyncio
from datetime import datetime, timezone
from sqlalchemy import delete, and_, or_
from app.core.database import AsyncSessionLocal
from app.models.token import RefreshToken
import logging

logger = logging.getLogger(__name__)

async def cleanup_expired_tokens():
    async with AsyncSessionLocal() as session:
        stmt = delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < datetime.now(timezone.utc),
                RefreshToken.revoked == True
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        logger.info("Cleaned up %d expired/revoked tokens", result.rowcount)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_expired_tokens())