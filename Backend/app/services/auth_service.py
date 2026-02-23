from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.core.exceptions import UnauthorizedException
from app.models.token import RefreshToken
from app.repositories.user_repo import UserRepository
from app.repositories.token_repo import TokenRepository
from app.core.security import hash_token, verify_password, create_access_token, create_refresh_token
from app.core.config import get_settings
from app.schemas.token import TokenResponse
from jose import jwt, JWTError
import logging

logger = logging.getLogger(__name__)



class AuthService:
    def __init__(self, user_repo: UserRepository, token_repo: TokenRepository):
        self.user_repo = user_repo
        self.token_repo = token_repo


    async def login(self ,identifier: str, password: str) -> TokenResponse:
        settings = get_settings()
        user = await self.user_repo.get_by_email_or_username(identifier)
        if not user:
            logger.warning("Login failed: user not found for identifier=%s", identifier)
            raise UnauthorizedException(detail="Incorrect email/username or password")
        if not verify_password(password, user.password_hash):
            logger.warning("Login failed: invalid password for user_id=%s", user.id)
            raise UnauthorizedException(detail="Incorrect email/username or password")
        logger.info("User logged in successfully: user_id=%s", user.id)
        access_token_str = create_access_token(user.id)
        refresh_token_str = create_refresh_token(user.id)
        refresh_token_hash = hash_token(refresh_token_str)
        db_token = RefreshToken(token_hash = refresh_token_hash, user_id=user.id, expires_at= datetime.now(timezone.utc) + 
                             timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
        await self.token_repo.create(db_token)
        logger.info("Tokens created and stored for user_id=%s", user.id)
        return TokenResponse(access_token=access_token_str, refresh_token= refresh_token_str, token_type="bearer")


    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        settings = get_settings()
        try:
            payload = jwt.decode(refresh_token,settings.SECRET_KEY,[ settings.ALGORITHM])
            if payload.get("type") != "refresh":
                raise UnauthorizedException(detail="Invalid token type.")
            subject = payload.get('sub')
        except JWTError:
            raise UnauthorizedException(detail="Invalid refresh token")
        
        stored_token = await self.token_repo.get_by_token(refresh_token, for_update=True)    
        if not stored_token:
            logger.warning("Refresh token not found")
            raise UnauthorizedException(detail="Refresh token not found")
        if stored_token.revoked:
            logger.warning("Refresh token revoked")
            raise UnauthorizedException(detail="Token revoked")
        if stored_token.expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
            logger.warning("Refresh token expired")
            raise UnauthorizedException(detail="Token expired")
        

        new_access_token = create_access_token(subject)
        new_refresh_token_str = create_refresh_token(subject)
        new_refresh_token_hash = hash_token(new_refresh_token_str)

        new_db_token = RefreshToken(
            token_hash=new_refresh_token_hash,
            user_id=UUID(subject),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )

        logger.info("Refresh token valid and The new tokens are being created for user_id=%s", subject)
        stored_token.revoked = True
        await self.token_repo.create(new_db_token)
        await self.token_repo.update(stored_token)

        logger.info("New tokens created and stored for user_id=%s", subject)
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token_str,
            token_type="bearer"
        )

    async def logout(self, refresh_token: str) -> None:
        revoked = await self.token_repo.revoke_token(refresh_token)
        if not revoked:
            logger.warning("Logout attempted with invalid or already revoked token")
            raise UnauthorizedException(detail="Invalid or already revoked token")
        logger.info("User logged out, refresh token revoked")
        
        
        

        

  
        

