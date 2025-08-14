import os
from dotenv import load_dotenv
load_dotenv()

def env(name: str, default: str | None = None, required: bool = False):
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing env: {name}")
    return val

DB_HOST = env("DB_HOST", "localhost")
DB_PORT = env("DB_PORT", "5432")
DB_NAME = env("DB_NAME", required=True)
DB_USER = env("DB_USER", required=True)
DB_PASSWORD = env("DB_PASSWORD", required=True)

FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "http://localhost:3000")
FRONTEND_CALLBACK_URL = env("FRONTEND_CALLBACK_URL", "http://localhost:4200/auth/linkedin")


JWT_SECRET = env("JWT_SECRET", required=True)
JWT_ALGORITHM = env("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(env("JWT_EXPIRY_MINUTES", "60"))
LOG_LEVEL   = env("LOG_LEVEL", "INFO")
DEV_VERBOSE = env("DEV_VERBOSE", "false").lower() == "true"
GEMINI_API_KEY = env("GEMINI_API_KEY", "")
