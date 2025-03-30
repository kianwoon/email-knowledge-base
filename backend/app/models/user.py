from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: List[str]


class UserBase(BaseModel):
    email: EmailStr
    display_name: str


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    ms_token_data: Optional[TokenData] = None
    is_active: bool = True
    preferences: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class UserInDB(User):
    hashed_password: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime


class AuthResponse(BaseModel):
    user: User
    token: Token
