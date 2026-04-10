from pydantic import BaseModel, EmailStr


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackResponse(BaseModel):
    user_id: str
    email: EmailStr
    connected: bool = True


class AuthMeResponse(BaseModel):
    user_id: str
    email: EmailStr


class LogoutResponse(BaseModel):
    success: bool = True
