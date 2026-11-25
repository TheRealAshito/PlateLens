"""Fixtures isoladas para testes do PlateLens."""

import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import get_settings
from backend.app.database import init_db
from backend.app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "platelens_data"
    monkeypatch.setenv("PLATELENS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    init_db(get_settings())
    with TestClient(app) as test_client:
        yield test_client


def make_test_jpeg_bytes(width: int = 1600, height: int = 1200) -> bytes:
    img = Image.new("RGB", (width, height), color=(210, 140, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
