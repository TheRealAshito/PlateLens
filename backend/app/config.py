"""Configurações de ambiente e caminhos persistentes do PlateLens."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Configurações resolvidas a partir de variáveis de ambiente."""

    data_dir: Path
    uploads_dir: Path
    db_path: Path
    vision_provider: str
    gemini_api_key: str
    gemini_model: str
    gemini_fallback_model: str
    ollama_base_url: str
    ollama_model: str
    max_image_side_px: int
    max_upload_bytes: int
    port: int


def get_settings() -> Settings:
    """Carrega configurações atuais do ambiente a cada chamada (facilita testes)."""
    default_data = BASE_DIR / "data"
    data_dir = Path(os.getenv("PLATELENS_DATA_DIR", str(default_data))).resolve()
    uploads_dir = data_dir / "uploads"
    db_path = data_dir / "platelens.db"

    return Settings(
        data_dir=data_dir,
        uploads_dir=uploads_dir,
        db_path=db_path,
        vision_provider=os.getenv("VISION_PROVIDER", "gemini").strip().lower() or "gemini",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash",
        gemini_fallback_model=os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite",
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b").strip() or "qwen2.5vl:3b",
        max_image_side_px=max(512, int(os.getenv("MAX_IMAGE_SIDE_PX", "1280"))),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024))),
        port=int(os.getenv("PORT", "8502")),
    )


def ensure_directories(settings: Settings | None = None) -> Settings:
    """Garante existência dos diretórios locais persistentes."""
    cfg = settings or get_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.uploads_dir.mkdir(parents=True, exist_ok=True)
    return cfg
