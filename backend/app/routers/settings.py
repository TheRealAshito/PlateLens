"""Endpoints de configuração do provedor de IA (sem expor chaves secretas)."""

from fastapi import APIRouter, Body
from pydantic import BaseModel

from backend.app.config import get_settings
from backend.app.database import get_connection
from backend.app.schemas import AiSettingsStatus, UpdateAiSettingsRequest
from backend.app.services.settings_service import (
    get_effective_ai_config,
    get_public_ai_status,
    update_ai_settings,
)
from backend.app.services.vision_provider import test_gemini_api_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


class TestKeyRequest(BaseModel):
    gemini_api_key: str = ""


@router.get("/ai", response_model=AiSettingsStatus)
def get_ai_settings():
    settings = get_settings()
    with get_connection(settings) as conn:
        return get_public_ai_status(conn, settings)


@router.put("/ai", response_model=AiSettingsStatus)
def save_ai_settings(payload: UpdateAiSettingsRequest):
    settings = get_settings()
    with get_connection(settings) as conn:
        return update_ai_settings(conn, payload, settings)


@router.post("/ai/test")
async def validate_ai_key(payload: TestKeyRequest = Body(default=TestKeyRequest())):
    settings = get_settings()
    key_to_test = payload.gemini_api_key.strip()
    if not key_to_test:
        with get_connection(settings) as conn:
            key_to_test = get_effective_ai_config(conn, settings).gemini_api_key
    ok, message = await test_gemini_api_key(key_to_test)
    return {"ok": ok, "message": message}
