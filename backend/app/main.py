from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.database import async_session_factory, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: database engine is initialized via module import
    # Seed default admin account (idempotent)
    async with async_session_factory() as db:
        from app.utils.seed import seed_admin
        await seed_admin(db)
        await db.commit()
    yield
    # Shutdown: close shared HTTP client and dispose database engine
    from app.services.avatar_service import close_client
    await close_client()
    await engine.dispose()


app = FastAPI(
    title="Guess API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — TODO: tighten methods/headers for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# Register API v1 router
app.include_router(api_v1_router)
