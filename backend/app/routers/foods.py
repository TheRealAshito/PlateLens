"""Endpoints de consulta e cadastro na Tabela TACO local."""

import sqlite3
from fastapi import APIRouter, HTTPException, Query

from backend.app.config import get_settings
from backend.app.database import get_connection, normalize_text
from backend.app.schemas import CreateCustomFoodRequest, TacoFoodResponse
from backend.app.services.nutrition_engine import search_taco_foods

router = APIRouter(prefix="/api/foods", tags=["foods"])


@router.get("/search", response_model=list[TacoFoodResponse])
def search_foods(
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=60),
    limit: int = Query(default=25, ge=1, le=100),
):
    settings = get_settings()
    with get_connection(settings) as conn:
        items = search_taco_foods(conn, q, limit=limit * 2 if category else limit)
        if category:
            cat_norm = normalize_text(category)
            items = [i for i in items if normalize_text(i["category"]) == cat_norm]
        return [
            TacoFoodResponse(
                id=i["id"],
                name=i["name"],
                category=i["category"],
                kcal_per_100g=i["kcal_per_100g"],
                protein_g=i["protein_g"],
                carbs_g=i["carbs_g"],
                fat_g=i["fat_g"],
                fiber_g=i["fiber_g"],
                household_unit_label=i["household_unit_label"],
                household_unit_grams=i["household_unit_grams"],
                is_custom=bool(i["is_custom"]),
            )
            for i in items[:limit]
        ]


@router.get("/categories", response_model=list[str])
def list_categories():
    settings = get_settings()
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM taco_foods ORDER BY category ASC"
        ).fetchall()
        return [row["category"] for row in rows]


@router.post("", response_model=TacoFoodResponse, status_code=201)
def create_custom_food(payload: CreateCustomFoodRequest):
    settings = get_settings()
    with get_connection(settings) as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO taco_foods (
                    name, name_normalized, category,
                    kcal_per_100g, protein_g, carbs_g, fat_g, fiber_g,
                    household_unit_label, household_unit_grams, is_custom
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    payload.name.strip(),
                    normalize_text(payload.name),
                    payload.category.strip(),
                    payload.kcal_per_100g,
                    payload.protein_g,
                    payload.carbs_g,
                    payload.fat_g,
                    payload.fiber_g,
                    payload.household_unit_label.strip(),
                    payload.household_unit_grams,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Já existe um alimento cadastrado com esse nome.",
            ) from exc

        row = conn.execute(
            "SELECT * FROM taco_foods WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return TacoFoodResponse(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            kcal_per_100g=row["kcal_per_100g"],
            protein_g=row["protein_g"],
            carbs_g=row["carbs_g"],
            fat_g=row["fat_g"],
            fiber_g=row["fiber_g"],
            household_unit_label=row["household_unit_label"],
            household_unit_grams=row["household_unit_grams"],
            is_custom=bool(row["is_custom"]),
        )
