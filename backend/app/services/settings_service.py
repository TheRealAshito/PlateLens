"""Gerenciamento seguro de configurações de IA (sem expor chaves na API)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal, Optional

from backend.app.config import Settings
from backend.app.database import utc_now_iso
from backend.app.schemas import AiSettingsStatus, UpdateAiSettingsRequest


@dataclass(frozen=True)
class EffectiveAiConfig:
    vision_provider: str
    gemini_api_key: str
    gemini_model: str
    gemini_fallback_model: str
    ollama_base_url: str
    ollama_model: str
    key_source: Literal["env", "database", "none"]
    onboarding_dismissed: bool


def mask_secret(secret: str) -> Optional[str]:
    if not secret:
        return None
    if len(secret) <= 8:
        return "••••"
    return f"{secret[:4]}••••{secret[-4:]}"


def _read_db_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def get_effective_ai_config(conn: sqlite3.Connection, settings: Settings) -> EffectiveAiConfig:
    """Resolve configuração efetiva priorizando valores salvos na UI sobre .env."""
    stored = _read_db_settings(conn)

    provider = stored.get("vision_provider") or settings.vision_provider
    db_key = stored.get("gemini_api_key", "").strip()
    env_key = settings.gemini_api_key.strip()

    if db_key:
        effective_key = db_key
        key_source: Literal["env", "database", "none"] = "database"
    elif env_key:
        effective_key = env_key
        key_source = "env"
    else:
        effective_key = ""
        key_source = "none"

    gemini_model = stored.get("gemini_model") or settings.gemini_model
    gemini_fallback = stored.get("gemini_fallback_model") or settings.gemini_fallback_model
    ollama_url = (stored.get("ollama_base_url") or settings.ollama_base_url).rstrip("/")
    ollama_model = stored.get("ollama_model") or settings.ollama_model
    dismissed = stored.get("onboarding_dismissed", "0") == "1"

    return EffectiveAiConfig(
        vision_provider=provider,
        gemini_api_key=effective_key,
        gemini_model=gemini_model,
        gemini_fallback_model=gemini_fallback,
        ollama_base_url=ollama_url,
        ollama_model=ollama_model,
        key_source=key_source,
        onboarding_dismissed=dismissed,
    )


def is_ai_configured(cfg: EffectiveAiConfig) -> bool:
    if cfg.vision_provider == "gemini":
        return bool(cfg.gemini_api_key)
    if cfg.vision_provider == "ollama":
        return bool(cfg.ollama_base_url)
    if cfg.vision_provider == "mock":
        return True
    return False


def get_public_ai_status(conn: sqlite3.Connection, settings: Settings) -> AiSettingsStatus:
    cfg = get_effective_ai_config(conn, settings)
    configured = is_ai_configured(cfg)
    needs_setup = (cfg.vision_provider in ("gemini", "ollama")) and (not configured)
    return AiSettingsStatus(
        vision_provider=cfg.vision_provider,
        ai_configured=configured,
        needs_setup=needs_setup,
        onboarding_dismissed=cfg.onboarding_dismissed,
        key_source=cfg.key_source,
        masked_key=mask_secret(cfg.gemini_api_key),
        gemini_model=cfg.gemini_model,
        gemini_fallback_model=cfg.gemini_fallback_model,
        ollama_base_url=cfg.ollama_base_url,
        ollama_model=cfg.ollama_model,
    )


def update_ai_settings(
    conn: sqlite3.Connection,
    payload: UpdateAiSettingsRequest,
    settings: Settings,
) -> AiSettingsStatus:
    now = utc_now_iso()

    def _upsert(key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    if payload.vision_provider is not None:
        _upsert("vision_provider", payload.vision_provider)
    if payload.clear_gemini_api_key:
        conn.execute("DELETE FROM app_settings WHERE key = 'gemini_api_key'")
    elif payload.gemini_api_key is not None and payload.gemini_api_key.strip():
        _upsert("gemini_api_key", payload.gemini_api_key.strip())
    if payload.gemini_model is not None and payload.gemini_model.strip():
        _upsert("gemini_model", payload.gemini_model.strip())
    if payload.gemini_fallback_model is not None and payload.gemini_fallback_model.strip():
        _upsert("gemini_fallback_model", payload.gemini_fallback_model.strip())
    if payload.ollama_base_url is not None:
        _upsert("ollama_base_url", payload.ollama_base_url.strip().rstrip("/"))
    if payload.ollama_model is not None and payload.ollama_model.strip():
        _upsert("ollama_model", payload.ollama_model.strip())
    if payload.onboarding_dismissed is not None:
        _upsert("onboarding_dismissed", "1" if payload.onboarding_dismissed else "0")

    return get_public_ai_status(conn, settings)
