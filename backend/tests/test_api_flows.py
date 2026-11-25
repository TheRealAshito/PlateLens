"""Testes de integração da API, onboarding sem chave, fluxo de foto e fallback 429."""

import asyncio
import json
import httpx
import pytest

from backend.app.config import get_settings
from backend.app.services.vision_provider import GeminiVisionProvider
from backend.tests.conftest import make_test_jpeg_bytes


def test_first_boot_requires_api_key_and_never_leaks_secret(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["taco_count"] >= 100
    assert body["ai_configured"] is False
    assert body["needs_setup"] is True

    status = client.get("/api/settings/ai").json()
    assert status["needs_setup"] is True
    assert status["key_source"] == "none"
    assert status["masked_key"] is None

    # Tentar analisar foto sem chave deve retornar 428 e limpar upload temporário
    resp = client.post(
        "/api/meals/analyze",
        files={"file": ("prato.jpg", make_test_jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 428
    assert resp.json()["detail"]["code"] == "API_KEY_REQUIRED"
    uploads_dir = get_settings().uploads_dir
    assert list(uploads_dir.glob("*.jpg")) == []

    # Salvar chave pela WebUI mascara o segredo na resposta
    secret_key = "AIzaSyTestExampleKey987654321"
    put_resp = client.put("/api/settings/ai", json={"gemini_api_key": secret_key})
    assert put_resp.status_code == 200
    saved = put_resp.json()
    assert saved["ai_configured"] is True
    assert saved["needs_setup"] is False
    assert saved["key_source"] == "database"
    assert saved["masked_key"] == "AIza••••4321"
    assert secret_key not in json.dumps(saved)


def test_analyze_recalculate_crud_repeat_and_stats(client, monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "mock")

    # 1. Analisar foto com MockVisionProvider
    analyze_resp = client.post(
        "/api/meals/analyze",
        files={"file": ("almoco.jpg", make_test_jpeg_bytes(2000, 1500), "image/jpeg")},
        data={"meal_context": "prato feito", "plate_size": "normal", "model_mode": "precise"},
    )
    assert analyze_resp.status_code == 200
    analysis = analyze_resp.json()
    assert analysis["ai_provider_used"] == "mock"
    assert len(analysis["items"]) == 3
    assert all(item["source"] == "taco" for item in analysis["items"])
    assert analysis["totals"]["total_kcal"] > 400
    photo_filename = analysis["photo_filename"]

    # 2. Recalcular alterando gramas do arroz (150g -> 200g)
    items_payload = [
        {
            "taco_food_id": item["taco_food_id"],
            "label": item["label"],
            "grams": 200.0 if "Arroz" in item["label"] else item["grams"],
            "per_100g": item["per_100g"],
            "confidence": item["confidence"],
            "source": item["source"],
        }
        for item in analysis["items"]
    ]
    recalc_resp = client.post("/api/meals/recalculate", json={"items": items_payload})
    assert recalc_resp.status_code == 200
    recalc_totals = recalc_resp.json()["totals"]
    assert recalc_totals["total_kcal"] > analysis["totals"]["total_kcal"]

    # 3. Salvar refeição no diário
    create_resp = client.post(
        "/api/meals",
        json={
            "eaten_date": "2026-11-24",
            "eaten_time": "12:30",
            "meal_type": "almoco",
            "title": "PF de Frango",
            "photo_filename": photo_filename,
            "notes": "Sem azeite extra",
            "ai_provider_used": "mock",
            "ai_model_used": "mock-precise",
            "warnings": analysis["warnings"],
            "is_favorite": True,
            "items": items_payload,
        },
    )
    assert create_resp.status_code == 201
    meal = create_resp.json()
    meal_id = meal["id"]

    # 4. Listar refeições do dia e verificar foto acessível
    day_resp = client.get("/api/meals?date=2026-11-24")
    assert day_resp.status_code == 200
    day_data = day_resp.json()
    assert len(day_data["meals"]) == 1
    assert day_data["day_totals"]["kcal"] == meal["total_kcal"]

    img_resp = client.get(meal["photo_url"])
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"] == "image/jpeg"

    # Path traversal na rota de uploads deve falhar
    bad_img = client.get("/api/uploads/..%2F..%2Fetc%2Fpasswd")
    assert bad_img.status_code in (400, 404)

    # 5. Repetir refeição cria cópia compartilhando foto
    repeat_resp = client.post(f"/api/meals/{meal_id}/repeat?eaten_date=2026-11-24&meal_type=jantar")
    assert repeat_resp.status_code == 201
    cloned_id = repeat_resp.json()["id"]

    # Deletar original mantém a foto porque o clone ainda referencia
    del1 = client.delete(f"/api/meals/{meal_id}")
    assert del1.status_code == 200
    assert client.get(meal["photo_url"]).status_code == 200

    # Deletar clone remove a foto órfã do disco
    del2 = client.delete(f"/api/meals/{cloned_id}")
    assert del2.status_code == 200
    assert client.get(meal["photo_url"]).status_code == 404


def test_goals_tdee_and_custom_food(client):
    tdee_resp = client.post(
        "/api/goals/calculate-tdee",
        json={
            "sex": "F",
            "age": 28,
            "weight_kg": 62.0,
            "height_cm": 165.0,
            "activity_level": "light",
            "goal_mode": "maintain",
        },
    )
    assert tdee_resp.status_code == 200
    plan = tdee_resp.json()

    upd = client.put(
        "/api/goals",
        json={
            "sex": "F",
            "age": 28,
            "weight_kg": 62.0,
            "height_cm": 165.0,
            "activity_level": "light",
            "goal_mode": "maintain",
            "daily_kcal_goal": plan["recommended_kcal"],
            "protein_goal_g": plan["protein_goal_g"],
            "carbs_goal_g": plan["carbs_goal_g"],
            "fat_goal_g": plan["fat_goal_g"],
            "fiber_goal_g": plan["fiber_goal_g"],
        },
    )
    assert upd.status_code == 200
    assert upd.json()["daily_kcal_goal"] == plan["recommended_kcal"]

    custom = client.post(
        "/api/foods",
        json={
            "name": "Iogurte proteico caseiro",
            "category": "Personalizados",
            "kcal_per_100g": 75.0,
            "protein_g": 10.0,
            "carbs_g": 5.0,
            "fat_g": 1.5,
            "fiber_g": 0.0,
            "household_unit_label": "1 pote",
            "household_unit_grams": 160.0,
        },
    )
    assert custom.status_code == 201
    search = client.get("/api/foods/search?q=iogurte+proteico")
    assert search.status_code == 200
    assert any(f["name"] == "Iogurte proteico caseiro" for f in search.json())


def test_gemini_provider_automatic_429_fallback():
    called_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_urls.append(str(request.url))
        assert request.headers.get("x-goog-api-key") == "AIzaDummyKey"
        if "gemini-3.6-flash" in str(request.url):
            return httpx.Response(429, json={"error": {"message": "Quota exceeded"}})
        payload = {
            "plate_summary": "Arroz e ovo",
            "overall_confidence": "high",
            "warnings": [],
            "items": [
                {
                    "name": "Arroz branco cozido",
                    "search_query": "arroz branco cozido",
                    "estimated_grams": 120,
                    "portion_label": "5 colheres",
                    "confidence": 0.9,
                    "fallback_per_100g": {
                        "kcal": 128,
                        "protein_g": 2.5,
                        "carbs_g": 28.1,
                        "fat_g": 0.2,
                        "fiber_g": 1.6,
                    },
                }
            ],
        }
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]},
        )

    provider = GeminiVisionProvider(
        api_key="AIzaDummyKey",
        primary_model="gemini-3.6-flash",
        fallback_model="gemini-3.5-flash-lite",
        transport=httpx.MockTransport(handler),
    )
    res = asyncio.run(provider.analyze_plate(make_test_jpeg_bytes(400, 400)))
    assert len(called_urls) == 2
    assert "gemini-3.6-flash" in called_urls[0]
    assert "gemini-3.5-flash-lite" in called_urls[1]
    assert res.used_fallback_model is True
    assert res.model_used == "gemini-3.5-flash-lite"
