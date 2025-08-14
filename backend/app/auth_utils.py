import time
from passlib.hash import bcrypt
from jose import jwt
from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_MINUTES

def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)

def create_access_token(sub: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "iat": now, "exp": now + JWT_EXPIRY_MINUTES * 60}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
