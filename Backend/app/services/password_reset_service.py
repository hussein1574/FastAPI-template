import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.exceptions import AppException, NotFoundException
from app.core.security import get_password_hash, hash_token
from app.models.password_reset import PasswordResetToken
from app.repositories.password_reset_repo import PasswordResetRepository
from app.repositories.token_repo import TokenRepository
from app.repositories.user_repo import UserRepository
import logging

logger = logging.getLogger(__name__)


class PasswordResetService:
    def __init__(
        self,
        user_repo: UserRepository,
        password_reset_repo: PasswordResetRepository,
        token_repo: TokenRepository,
    ):
        self.user_repo = user_repo
        self.password_reset_repo = password_reset_repo
        self.token_repo = token_repo

    async def request_reset(self, email: str) -> str | None:
        """
        Generate a password reset token for the given email.
        Returns the raw token string if the user exists, None otherwise.
        The caller should always return a generic success message to prevent email enumeration.
        """
        settings = get_settings()
        user = await self.user_repo.get_by_email(email)

        if not user:
            logger.info("Password reset requested for non-existent email: %s", email)
            return None

        # Revoke any existing unused reset tokens for this user
        await self.password_reset_repo.revoke_all_for_user(user.id)

        # Generate a secure token
        raw_token = secrets.token_urlsafe(32)
        token_hash_value = hash_token(raw_token)

        reset_token = PasswordResetToken(
            token_hash=token_hash_value,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )

        await self.password_reset_repo.create(reset_token)

        # Log the token for development purposes.
        # In production, replace this with an email sender.
        logger.info(
            "Password reset token generated for user_id=%s | token=%s",
            user.id,
            raw_token,
        )

        return raw_token

    async def confirm_reset(self, token: str, new_password: str) -> None:
        """
        Validate the reset token and update the user's password.
        Revokes all existing refresh tokens to force re-login.
        """
        stored_token = await self.password_reset_repo.get_by_token(token)

        if not stored_token:
            logger.warning("Password reset attempted with invalid token")
            raise AppException(detail="Invalid or expired reset token", status_code=400)

        if stored_token.used:
            logger.warning("Password reset attempted with already-used token")
            raise AppException(detail="Invalid or expired reset token", status_code=400)

        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            logger.warning("Password reset attempted with expired token")
            raise AppException(detail="Invalid or expired reset token", status_code=400)

        # Get the user
        user = await self.user_repo.get_by_id(stored_token.user_id)
        if not user:
            logger.error("Password reset token references non-existent user_id=%s", stored_token.user_id)
            raise NotFoundException(detail="User not found")

        # Update password
        user.password_hash = get_password_hash(new_password)
        await self.user_repo.update(user)

        # Mark token as used
        await self.password_reset_repo.mark_used(stored_token)

        # Revoke all refresh tokens for this user (force re-login)
        await self.token_repo.revoke_all_for_user(stored_token.user_id)

        logger.info("Password reset successful for user_id=%s", stored_token.user_id)
