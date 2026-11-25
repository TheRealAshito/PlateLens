"""Motor determinístico de nutrição (Tabela TACO + calculadora TMB/TDEE)."""

from __future__ import annotations

import sqlite3
from typing import Optional

from backend.app.database import normalize_text
from backend.app.schemas import (
    ActivityLevel,
    GoalMode,
    MealItemDraft,
    MealTotals,
    Per100gSchema,
    RecalculateItemInput,
    SexType,
    TdeeCalculateResponse,
)

ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_DELTAS: dict[GoalMode, float] = {
    "lose": -400.0,
    "maintain": 0.0,
    "gain": 300.0,
}


def calculate_item_macros(per_100g: Per100gSchema, grams: float) -> dict[str, float]:
    """Calcula calorias e macros proporcionais ao peso em gramas."""
    if grams < 0:
        raise ValueError("grams deve ser maior ou igual a zero")
    factor = grams / 100.0
    return {
        "kcal": round(per_100g.kcal * factor, 1),
        "protein_g": round(per_100g.protein_g * factor, 1),
        "carbs_g": round(per_100g.carbs_g * factor, 1),
        "fat_g": round(per_100g.fat_g * factor, 1),
        "fiber_g": round(per_100g.fiber_g * factor, 1),
    }


def search_taco_foods(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    """Busca alimentos na Tabela TACO ignorando acentos e capitalização."""
    q_norm = normalize_text(query)
    rows = conn.execute("SELECT * FROM taco_foods ORDER BY name ASC").fetchall()
    if not q_norm:
        return [dict(r) for r in rows[:limit]]

    tokens = q_norm.split()
    scored: list[tuple[float, dict]] = []
    for row in rows:
        item = dict(row)
        name_norm = item["name_normalized"]
        score = 0.0
        if name_norm == q_norm:
            score += 100.0
        elif name_norm.startswith(q_norm):
            score += 60.0
        elif q_norm in name_norm:
            score += 40.0

        matched_tokens = sum(1 for tok in tokens if tok in name_norm)
        if matched_tokens == 0 and score == 0:
            continue
        score += matched_tokens * 18.0
        if matched_tokens == len(tokens):
            score += 20.0
        # Desempate favorece nomes mais diretos
        score -= len(name_norm) * 0.05
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
    return [item for _, item in scored[:limit]]


def match_taco_food(
    conn: sqlite3.Connection,
    search_query: str,
    fallback_name: str = "",
) -> Optional[dict]:
    """Encontra o melhor alimento correspondente na Tabela TACO."""
    for candidate in (search_query, fallback_name):
        q_norm = normalize_text(candidate)
        if not q_norm:
            continue
        tokens = [tok for tok in q_norm.split() if len(tok) >= 2]
        if not tokens:
            continue
        matches = search_taco_foods(conn, candidate, limit=3)
        if not matches:
            continue
        top = matches[0]
        top_norm = top["name_normalized"]
        overlap = sum(1 for tok in tokens if tok in top_norm)
        # Exige match mínimo de pelo menos 1 token significativo ou substring direta
        if q_norm in top_norm or overlap >= max(1, len(tokens) // 2):
            return top
    return None


def resolve_and_calculate_items(
    conn: sqlite3.Connection,
    raw_items: list[RecalculateItemInput],
) -> tuple[list[MealItemDraft], MealTotals]:
    """Normaliza itens (puxando TACO quando referenciado) e calcula totais do prato."""
    resolved: list[MealItemDraft] = []

    for item in raw_items:
        taco_row: Optional[dict] = None
        if item.taco_food_id is not None:
            row = conn.execute(
                "SELECT * FROM taco_foods WHERE id = ?",
                (item.taco_food_id,),
            ).fetchone()
            if row is not None:
                taco_row = dict(row)

        if taco_row is not None:
            per_100g = Per100gSchema(
                kcal=taco_row["kcal_per_100g"],
                protein_g=taco_row["protein_g"],
                carbs_g=taco_row["carbs_g"],
                fat_g=taco_row["fat_g"],
                fiber_g=taco_row["fiber_g"],
            )
            source = "taco" if item.source != "manual" else "manual"
            unit_label = taco_row["household_unit_label"]
            unit_grams = taco_row["household_unit_grams"]
        elif item.per_100g is not None:
            per_100g = item.per_100g
            source = item.source
            unit_label = None
            unit_grams = None
        else:
            raise ValueError(f"Item '{item.label}' sem referência TACO nem valores por 100g")

        macros = calculate_item_macros(per_100g, item.grams)
        resolved.append(
            MealItemDraft(
                taco_food_id=taco_row["id"] if taco_row else None,
                label=item.label,
                grams=round(item.grams, 1),
                kcal=macros["kcal"],
                protein_g=macros["protein_g"],
                carbs_g=macros["carbs_g"],
                fat_g=macros["fat_g"],
                fiber_g=macros["fiber_g"],
                per_100g=per_100g,
                confidence=round(item.confidence, 2),
                source=source,
                household_unit_label=unit_label,
                household_unit_grams=unit_grams,
            )
        )

    totals = compute_meal_totals(resolved)
    return resolved, totals


def compute_meal_totals(items: list[MealItemDraft]) -> MealTotals:
    """Soma nutrientes dos itens e calcula faixa estimada de incerteza calórica."""
    total_kcal = round(sum(i.kcal for i in items), 1)
    total_protein = round(sum(i.protein_g for i in items), 1)
    total_carbs = round(sum(i.carbs_g for i in items), 1)
    total_fat = round(sum(i.fat_g for i in items), 1)
    total_fiber = round(sum(i.fiber_g for i in items), 1)

    if not items:
        return MealTotals(
            total_kcal=0.0,
            total_kcal_min=0.0,
            total_kcal_max=0.0,
            total_protein_g=0.0,
            total_carbs_g=0.0,
            total_fat_g=0.0,
            total_fiber_g=0.0,
            overall_confidence="low",
        )

    # Margem ponderada pelas calorias e confiança de cada item
    weighted_margin = 0.0
    kcal_base = max(total_kcal, 1.0)
    for item in items:
        base_spread = 0.12 if item.source != "ai_fallback" else 0.22
        uncertainty_penalty = (1.0 - item.confidence) * 0.20
        item_spread = min(0.35, base_spread + uncertainty_penalty)
        weighted_margin += item.kcal * item_spread

    spread_ratio = weighted_margin / kcal_base if total_kcal > 0 else 0.15
    kcal_min = round(max(0.0, total_kcal * (1.0 - spread_ratio)), 0)
    kcal_max = round(total_kcal * (1.0 + spread_ratio), 0)

    avg_conf = sum(i.confidence for i in items) / len(items)
    if avg_conf >= 0.8:
        overall_conf = "high"
    elif avg_conf >= 0.55:
        overall_conf = "medium"
    else:
        overall_conf = "low"

    return MealTotals(
        total_kcal=total_kcal,
        total_kcal_min=kcal_min,
        total_kcal_max=kcal_max,
        total_protein_g=total_protein,
        total_carbs_g=total_carbs,
        total_fat_g=total_fat,
        total_fiber_g=total_fiber,
        overall_confidence=overall_conf,
    )


def calculate_tdee_plan(
    sex: SexType,
    age: int,
    weight_kg: float,
    height_cm: float,
    activity_level: ActivityLevel,
    goal_mode: GoalMode,
) -> TdeeCalculateResponse:
    """Calcula TMB (Mifflin-St Jeor), TDEE e divisão recomendada de macros."""
    sex_offset = 5.0 if sex == "M" else -161.0
    bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + sex_offset
    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]
    delta = GOAL_DELTAS[goal_mode]
    recommended_kcal = max(1200.0, round(tdee + delta, 0))

    protein_per_kg = 1.8 if goal_mode in ("lose", "gain") else 1.6
    protein_g = round(weight_kg * protein_per_kg, 0)
    fat_kcal = recommended_kcal * 0.27
    fat_g = round(fat_kcal / 9.0, 0)

    remaining_kcal = max(0.0, recommended_kcal - (protein_g * 4.0) - (fat_g * 9.0))
    carbs_g = round(remaining_kcal / 4.0, 0)
    fiber_g = round(max(20.0, (recommended_kcal / 1000.0) * 14.0), 0)

    return TdeeCalculateResponse(
        bmr_kcal=round(bmr, 0),
        tdee_kcal=round(tdee, 0),
        recommended_kcal=recommended_kcal,
        protein_goal_g=protein_g,
        carbs_goal_g=carbs_g,
        fat_goal_g=fat_g,
        fiber_goal_g=fiber_g,
        goal_delta_kcal=delta,
    )
