# app/main.py
import logging, asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import FRONTEND_ORIGIN, LOG_LEVEL
from .db import init_pool
from .routes.auth import router as auth_router
from .routes.profile import router as profile_router
from .routes.content import router as content_router
from .routes.oauth_linkedin import router as linkedin_oauth_router
from app.jobs.scheduler import run_scheduled_poster

load_dotenv()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("startup")

app = FastAPI(title="LinkedIn AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# IMPORTANT: make startup async so we can create the task
@app.on_event("startup")
async def startup():
    try:
        init_pool()
        log.info("DB pool initialized")
    except Exception as e:
        log.error("DB pool init failed: %s", e)

    # start background scheduler
    app.state.scheduler_task = asyncio.create_task(run_scheduled_poster())

@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "scheduler_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

# Routers
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(content_router)
app.include_router(linkedin_oauth_router)

@app.get("/health")
def health():
    return {"ok": True}
