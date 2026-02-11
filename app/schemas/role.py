from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleInDB(RoleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Role(RoleInDB):
    pass 