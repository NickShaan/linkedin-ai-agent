from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import BaseModel
from typing import List, Optional

class SignupIn(BaseModel):
    name: str
    email: EmailStr
    country_code: str
    mobile: str
    linkedin_id: str
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

# NEW: token + message so FastAPI includes your message
class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    message: str

class ProfileIn(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    industries: List[str] = []
    goals: Optional[str] = None
    tone: List[str] = []
    keywords: List[str] = []
    
    @field_validator('industries', 'tone', 'keywords', mode='before')
    @classmethod
    def _csv_or_list(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            items = [x.strip() for x in v.split(',') if x.strip()]
            # empty string -> treat as omitted (leave unchanged)
            return items if items else None
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return v  # let Pydantic raise if it's something unexpected

class ProfileOut(ProfileIn):
    user_id: int

class ProvidersIn(BaseModel):
    gemini_key: str
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None