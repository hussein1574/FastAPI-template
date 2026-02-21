from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

class UserBase(BaseModel):
    email: EmailStr
    username: str
    name: str
    avatar: str | None = None

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        return value
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if len(value) < 3 or len(value) > 30:
            raise ValueError("Username must be between 3 and 30 characters long")
        if not value.isalnum() and not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return value


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    name: str | None = None
    avatar: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) < 3 or len(value) > 30:
            raise ValueError("Username must be between 3 and 30 characters long")
        if not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return value    

class UserResponse(UserBase):
    id: UUID

    model_config= ConfigDict(from_attributes=True)
