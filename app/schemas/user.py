from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    department_id: int
    role_id: int
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class User(UserInDB):
    pass 