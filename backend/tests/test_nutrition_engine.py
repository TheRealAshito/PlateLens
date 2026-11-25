"""Testes unitários do motor nutricional (Tabela TACO + TMB/TDEE)."""

import pytest

from backend.app.config import get_settings
from backend.app.database import get_connection, init_db
from backend.app.schemas import Per100gSchema
from backend.app.services.nutrition_engine import (
    calculate_item_macros,
    calculate_macros_for_calories,
    calculate_tdee_plan,
    match_taco_food,
    search_taco_foods,
)


def test_calculate_item_macros_proportional():
    per_100g = Per100gSchema(kcal=128.0, protein_g=2.5, carbs_g=28.1, fat_g=0.2, fiber_g=1.6)
    res = calculate_item_macros(per_100g, 150.0)
    assert res == {
        "kcal": 192.0,
        "protein_g": 3.8,
        "carbs_g": 42.2,
        "fat_g": 0.3,
        "fiber_g": 2.4,
    }


def test_calculate_item_macros_rejects_negative():
    per_100g = Per100gSchema(kcal=100, protein_g=10, carbs_g=10, fat_g=2)
    with pytest.raises(ValueError):
        calculate_item_macros(per_100g, -5.0)


def test_taco_search_accent_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATELENS_DATA_DIR", str(tmp_path / "data"))
    settings = get_settings()
    init_db(settings)

    with get_connection(settings) as conn:
        feijao = search_taco_foods(conn, "feijao carioca")
        assert len(feijao) >= 1
        assert "Feijão carioca" in feijao[0]["name"]

        pao = search_taco_foods(conn, "pao frances")
        assert len(pao) >= 1
        assert pao[0]["name"] == "Pão francês"

        match = match_taco_food(conn, "peito de frango grelhado", "Frango")
        assert match is not None
        assert match["name"] == "Peito de frango grelhado"


def test_calculate_tdee_plan_mifflin_st_jeor():
    plan = calculate_tdee_plan(
        sex="M",
        age=30,
        weight_kg=80.0,
        height_cm=180.0,
        activity_level="moderate",
        goal_mode="lose",
    )
    # TMB = 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
    assert plan.bmr_kcal == 1780.0
    # TDEE = 1780 * 1.55 = 2759
    assert plan.tdee_kcal == 2759.0
    # Deficit -400 => 2359
    assert plan.recommended_kcal == 2359.0
    assert plan.protein_goal_g == 144.0
    assert plan.fat_goal_g > 0
    assert plan.carbs_goal_g > 0


def test_calculate_tdee_respects_minimum_floor():
    plan = calculate_tdee_plan(
        sex="F",
        age=65,
        weight_kg=45.0,
        height_cm=150.0,
        activity_level="sedentary",
        goal_mode="lose",
    )
    assert plan.recommended_kcal >= 1200.0


def test_calculate_macros_for_calories_presets_and_cap():
    bal = calculate_macros_for_calories(1600.0, weight_kg=80.0, goal_mode="lose", preset="balanced")
    assert bal.protein_goal_g == 144.0
    assert bal.fat_goal_g == 48.0
    assert bal.carbs_goal_g == 148.0

    # Em corte agressivo com peso alto, proteína é limitada a 40% para manter carboidratos viáveis
    capped = calculate_macros_for_calories(1200.0, weight_kg=95.0, goal_mode="lose", preset="balanced")
    assert capped.protein_goal_g == 120.0
    assert capped.carbs_goal_g > 0

    zone = calculate_macros_for_calories(2000.0, weight_kg=75.0, preset="zone_30_40_30")
    assert zone.protein_goal_g == 150.0
    assert zone.carbs_goal_g == 200.0
    assert zone.fat_goal_g == 67.0

    low_carb = calculate_macros_for_calories(1800.0, weight_kg=75.0, preset="low_carb")
    assert low_carb.carbs_goal_g == 90.0
    assert low_carb.fat_goal_g > bal.fat_goal_g
