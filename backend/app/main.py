"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.api import auth, profile, cache, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB migrations / table creation on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Lazy Seeker API",
    description="Local job application assistant — Phase 1: Auth + Profile + Answer Cache",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(cache.router)
app.include_router(jobs.router)


@app.get("/health")
async def health():
    return {"status": "ok", "phase": 1}
