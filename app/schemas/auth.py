from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """
    JWT extraction & validation
    """
    user_id: Optional[UUID]
    username: Optional[str]
    role: Optional[str]

class UserCreate(BaseModel):
    """new user schema"""
    username: str
    password: str