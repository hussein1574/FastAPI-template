from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenRevokeRequest(BaseModel):
    refresh_token: str