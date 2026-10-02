from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, consent, prompts, records, reflections, resources, session
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(prompts.router)
app.include_router(session.router)
app.include_router(chat.router)
app.include_router(consent.router)
app.include_router(records.router)
app.include_router(reflections.router)
app.include_router(resources.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
