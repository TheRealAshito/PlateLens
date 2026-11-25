"""Endpoint de saúde e verificação de prontidão inicial."""

from fastapi import APIRouter

from backend.app.config import get_settings
from backend.app.database import get_connection
from backend.app.services.settings_service import get_public_ai_status

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    with get_connection(settings) as conn:
        taco_count = conn.execute("SELECT COUNT(*) FROM taco_foods").fetchone()[0]
        ai_status = get_public_ai_status(conn, settings)
    return {
        "status": "ok",
        "taco_count": taco_count,
        "ai_configured": ai_status.ai_configured,
        "needs_setup": ai_status.needs_setup,
        "vision_provider": ai_status.vision_provider,
    }
