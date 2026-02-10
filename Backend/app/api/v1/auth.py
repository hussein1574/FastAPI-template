from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from app.services.auth_service import AuthService
from app.api.deps import get_auth_service
from app.schemas.token import TokenResponse, TokenRefreshRequest, TokenRevokeRequest
from slowapi.util import get_remote_address
from starlette.requests import Request
from fastapi import status

router = APIRouter()

auth_service = Annotated[AuthService, Depends(get_auth_service)]


limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], service: auth_service) -> TokenResponse:
    return await service.login(form_data.username, form_data.password)

@router.post('/refresh', response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request,request_body: TokenRefreshRequest, service: auth_service) -> TokenResponse:
    return await service.refresh_access_token(request_body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def logout(request: Request, body: TokenRevokeRequest, service: auth_service):
    await service.logout(body.refresh_token)


