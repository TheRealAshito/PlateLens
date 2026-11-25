"""Aplicação principal FastAPI do PlateLens."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import BASE_DIR, get_settings
from backend.app.database import init_db
from backend.app.routers import foods, goals, health, meals, settings as settings_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "base-uri 'self'"
        )
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(get_settings())
    yield


app = FastAPI(title="PlateLens API", version="1.0.0", lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8502",
        "http://127.0.0.1:8502",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(settings_router.router)
app.include_router(foods.router)
app.include_router(goals.router)
app.include_router(meals.router)

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Endpoint não encontrado.")
    if not FRONTEND_DIST.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend ainda não compilado. Execute 'npm run build' em frontend/.",
        )

    dist_root = FRONTEND_DIST.resolve()
    candidate = (dist_root / full_path).resolve()
    if full_path and dist_root in candidate.parents and candidate.is_file():
        return FileResponse(candidate)

    index_file = dist_root / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="index.html não encontrado.")
