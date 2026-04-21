from pydantic import BaseModel, EmailStr


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'UserProfile'


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserProfile(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


LoginResponse.model_rebuild()
