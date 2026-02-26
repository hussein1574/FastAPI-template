from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.api.deps import get_auth_service, get_password_reset_service
from app.schemas.token import TokenResponse, TokenRefreshRequest, TokenRevokeRequest
from app.schemas.password_reset import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
from slowapi.util import get_remote_address
from starlette.requests import Request
from fastapi import status

router = APIRouter()

auth_service = Annotated[AuthService, Depends(get_auth_service)]
password_reset_service = Annotated[PasswordResetService, Depends(get_password_reset_service)]


limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], service: auth_service) -> TokenResponse:
    return await service.login(
        form_data.username,
        form_data.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

@router.post('/refresh', response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request,request_body: TokenRefreshRequest, service: auth_service) -> TokenResponse:
    return await service.refresh_access_token(
        request_body.refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def logout(request: Request, body: TokenRevokeRequest, service: auth_service):
    await service.logout(body.refresh_token)


@router.post("/password-reset/request", response_model=PasswordResetResponse)
@limiter.limit("3/minute")
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    service: password_reset_service,
) -> PasswordResetResponse:
    await service.request_reset(
        body.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    # Always return success to prevent email enumeration
    return PasswordResetResponse(message="If the email exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
@limiter.limit("5/minute")
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirm,
    service: password_reset_service,
) -> PasswordResetResponse:
    await service.confirm_reset(body.token, body.new_password)
    return PasswordResetResponse(message="Password has been reset successfully.")


