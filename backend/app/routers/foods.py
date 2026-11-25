"""Endpoints de consulta e cadastro na Tabela TACO local."""

import sqlite3
from fastapi import APIRouter, HTTPException, Query

from backend.app.config import get_settings
from backend.app.database import get_connection, normalize_text
from backend.app.schemas import (
    CreateCustomFoodRequest,
    TacoFoodResponse,
    UpdateCustomFoodRequest,
)
from backend.app.services.nutrition_engine import search_taco_foods

router = APIRouter(prefix="/api/foods", tags=["foods"])


def _row_to_food(row: sqlite3.Row) -> TacoFoodResponse:
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


@router.get("/custom", response_model=list[TacoFoodResponse])
def list_custom_foods():
    settings = get_settings()
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM taco_foods WHERE is_custom = 1 ORDER BY name ASC"
        ).fetchall()
        return [_row_to_food(r) for r in rows]


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
        return _row_to_food(row)


@router.put("/{food_id}", response_model=TacoFoodResponse)
def update_custom_food(food_id: int, payload: UpdateCustomFoodRequest):
    settings = get_settings()
    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT * FROM taco_foods WHERE id = ?",
            (food_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Alimento não encontrado.")
        if not existing["is_custom"]:
            raise HTTPException(
                status_code=403,
                detail="Apenas alimentos personalizados cadastrados por você podem ser editados.",
            )

        new_name = payload.name.strip() if payload.name is not None else existing["name"]
        new_category = (
            payload.category.strip() if payload.category is not None else existing["category"]
        )
        new_kcal = (
            payload.kcal_per_100g
            if payload.kcal_per_100g is not None
            else existing["kcal_per_100g"]
        )
        new_protein = (
            payload.protein_g if payload.protein_g is not None else existing["protein_g"]
        )
        new_carbs = payload.carbs_g if payload.carbs_g is not None else existing["carbs_g"]
        new_fat = payload.fat_g if payload.fat_g is not None else existing["fat_g"]
        new_fiber = payload.fiber_g if payload.fiber_g is not None else existing["fiber_g"]
        new_unit_label = (
            payload.household_unit_label.strip()
            if payload.household_unit_label is not None
            else existing["household_unit_label"]
        )
        new_unit_grams = (
            payload.household_unit_grams
            if payload.household_unit_grams is not None
            else existing["household_unit_grams"]
        )

        try:
            conn.execute(
                """
                UPDATE taco_foods
                SET name = ?, name_normalized = ?, category = ?,
                    kcal_per_100g = ?, protein_g = ?, carbs_g = ?, fat_g = ?, fiber_g = ?,
                    household_unit_label = ?, household_unit_grams = ?
                WHERE id = ?
                """,
                (
                    new_name,
                    normalize_text(new_name),
                    new_category,
                    new_kcal,
                    new_protein,
                    new_carbs,
                    new_fat,
                    new_fiber,
                    new_unit_label,
                    new_unit_grams,
                    food_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Já existe outro alimento cadastrado com esse nome.",
            ) from exc

        updated = conn.execute(
            "SELECT * FROM taco_foods WHERE id = ?",
            (food_id,),
        ).fetchone()
        return _row_to_food(updated)


@router.delete("/{food_id}")
def delete_custom_food(food_id: int):
    settings = get_settings()
    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT is_custom FROM taco_foods WHERE id = ?",
            (food_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Alimento não encontrado.")
        if not existing["is_custom"]:
            raise HTTPException(
                status_code=403,
                detail="Alimentos padrão da Tabela TACO não podem ser removidos.",
            )
        conn.execute("DELETE FROM taco_foods WHERE id = ?", (food_id,))
    return {"deleted": True, "id": food_id}
