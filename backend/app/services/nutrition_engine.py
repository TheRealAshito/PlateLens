"""Motor determinístico de nutrição (Tabela TACO + calculadora TMB/TDEE)."""

from __future__ import annotations

import sqlite3
from typing import Optional

from backend.app.database import normalize_text
from backend.app.schemas import (
    ActivityLevel,
    GoalMode,
    MacroPreset,
    MacroRecalculateResponse,
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


STOP_WORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos",
    "com", "sem", "ao", "aos", "em", "no", "na", "nos", "nas",
    "e", "ou", "por", "para",
}
FRIED_BREADED_TOKENS = {"frito", "frita", "empanado", "empanada", "milanesa", "parmegiana", "dore"}
LEAN_PREP_TOKENS = {"grelhado", "grelhada", "cozido", "cozida", "assado", "assada"}


def _meaningful_tokens(text_norm: str) -> list[str]:
    return [tok for tok in text_norm.split() if len(tok) >= 2 and tok not in STOP_WORDS]


def _has_semantic_conflict(query_tokens: set[str], target_tokens: set[str]) -> bool:
    """Evita matches incompatíveis entre preparos ou bases diferentes."""
    q_fried = bool(query_tokens & FRIED_BREADED_TOKENS)
    t_lean = bool(target_tokens & LEAN_PREP_TOKENS)
    t_fried = bool(target_tokens & FRIED_BREADED_TOKENS)
    q_lean = bool(query_tokens & LEAN_PREP_TOKENS)
    if (q_fried and t_lean and not t_fried) or (q_lean and t_fried and not t_lean):
        return True

    # Evita trocar base distinta (ex.: purê de mandioca vs purê de batata)
    if ("mandioca" in query_tokens or "aipim" in query_tokens) and "batata" in target_tokens and "mandioca" not in target_tokens:
        return True
    if "batata" in query_tokens and ("mandioca" in target_tokens or "aipim" in target_tokens) and "batata" not in target_tokens:
        return True
    if "zero" in query_tokens and "zero" not in target_tokens:
        return True
    return False


def match_taco_food(
    conn: sqlite3.Connection,
    search_query: str,
    fallback_name: str = "",
) -> Optional[dict]:
    """Encontra o melhor alimento correspondente na Tabela TACO sem forçar matches ruins."""
    for candidate in (search_query, fallback_name):
        q_norm = normalize_text(candidate)
        if not q_norm:
            continue
        tokens = _meaningful_tokens(q_norm)
        if not tokens:
            continue

        matches = search_taco_foods(conn, " ".join(tokens), limit=5)
        if not matches:
            continue

        query_set = set(tokens)
        for cand in matches:
            cand_norm = cand["name_normalized"]
            cand_tokens = set(_meaningful_tokens(cand_norm))
            if _has_semantic_conflict(query_set, cand_tokens):
                continue

            overlap = sum(1 for tok in tokens if tok in cand_tokens or tok in cand_norm)
            coverage = overlap / len(tokens)
            # Match exato / substring forte ou alta cobertura de tokens relevantes
            if q_norm == cand_norm or (q_norm in cand_norm and len(tokens) >= 1):
                return cand
            if len(tokens) <= 2 and overlap == len(tokens):
                return cand
            if len(tokens) >= 3 and coverage >= 0.67:
                return cand
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


def calculate_macros_for_calories(
    daily_kcal_goal: float,
    weight_kg: float,
    goal_mode: GoalMode = "lose",
    preset: MacroPreset = "balanced",
) -> MacroRecalculateResponse:
    """Reestrutura metas de proteína, carboidrato, gordura e fibra para um alvo calórico."""
    target_kcal = max(1000.0, float(daily_kcal_goal))

    if preset == "zone_30_40_30":
        protein_g = round((target_kcal * 0.30) / 4.0, 0)
        carbs_g = round((target_kcal * 0.40) / 4.0, 0)
        fat_g = round((target_kcal * 0.30) / 9.0, 0)
    elif preset == "low_carb":
        desired_protein_kcal = weight_kg * 1.8 * 4.0
        protein_kcal = min(desired_protein_kcal, target_kcal * 0.40)
        protein_g = round(protein_kcal / 4.0, 0)
        carbs_g = round((target_kcal * 0.20) / 4.0, 0)
        remaining_fat_kcal = max(0.0, target_kcal - (protein_g * 4.0) - (carbs_g * 4.0))
        fat_g = round(remaining_fat_kcal / 9.0, 0)
    else:
        if preset == "high_protein":
            protein_per_kg = 2.1
            max_prot_ratio = 0.45
            fat_ratio = 0.25
        else:
            protein_per_kg = 1.8 if goal_mode in ("lose", "gain") else 1.6
            max_prot_ratio = 0.40
            fat_ratio = 0.27

        desired_protein_kcal = weight_kg * protein_per_kg * 4.0
        protein_kcal = min(desired_protein_kcal, target_kcal * max_prot_ratio)
        protein_g = round(protein_kcal / 4.0, 0)
        fat_g = round((target_kcal * fat_ratio) / 9.0, 0)
        remaining_kcal = max(0.0, target_kcal - (protein_g * 4.0) - (fat_g * 9.0))
        carbs_g = round(remaining_kcal / 4.0, 0)

    fiber_g = round(max(20.0, (target_kcal / 1000.0) * 14.0), 0)
    water_goal_ml = int(min(5000, max(1500, round((weight_kg * 35.0) / 50.0) * 50)))
    macro_total = max(1.0, (protein_g * 4.0) + (carbs_g * 4.0) + (fat_g * 9.0))

    return MacroRecalculateResponse(
        daily_kcal_goal=round(target_kcal, 0),
        protein_goal_g=protein_g,
        carbs_goal_g=carbs_g,
        fat_goal_g=fat_g,
        fiber_goal_g=fiber_g,
        water_goal_ml=water_goal_ml,
        protein_pct=round((protein_g * 4.0 / macro_total) * 100.0, 1),
        carbs_pct=round((carbs_g * 4.0 / macro_total) * 100.0, 1),
        fat_pct=round((fat_g * 9.0 / macro_total) * 100.0, 1),
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

    macros = calculate_macros_for_calories(
        daily_kcal_goal=recommended_kcal,
        weight_kg=weight_kg,
        goal_mode=goal_mode,
        preset="balanced",
    )

    return TdeeCalculateResponse(
        bmr_kcal=round(bmr, 0),
        tdee_kcal=round(tdee, 0),
        recommended_kcal=recommended_kcal,
        protein_goal_g=macros.protein_goal_g,
        carbs_goal_g=macros.carbs_goal_g,
        fat_goal_g=macros.fat_goal_g,
        fiber_goal_g=macros.fiber_goal_g,
        water_goal_ml=macros.water_goal_ml,
        goal_delta_kcal=delta,
    )
