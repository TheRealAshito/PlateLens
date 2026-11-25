"""Endpoints de análise de prato por foto, CRUD de refeições e estatísticas."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.database import get_connection, utc_now_iso
from backend.app.schemas import (
    AnalyzeMealResponse,
    CreateMealRequest,
    MealItemDraft,
    MealTotals,
    ModelMode,
    Per100gSchema,
    RecalculateRequest,
    RecalculateResponse,
    UpdateMealRequest,
)
from backend.app.services.image_utils import (
    InvalidImageError,
    process_and_save_plate_image,
    resolve_safe_upload_path,
)
from backend.app.services.nutrition_engine import (
    calculate_item_macros,
    compute_meal_totals,
    match_taco_food,
    resolve_and_calculate_items,
)
from backend.app.services.settings_service import get_effective_ai_config
from backend.app.services.vision_provider import (
    VisionNotConfiguredError,
    VisionProviderError,
    build_vision_provider,
)

router = APIRouter(prefix="/api", tags=["meals"])


def _serialize_meal_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    item_rows = conn.execute(
        """
        SELECT mi.*, tf.household_unit_label, tf.household_unit_grams
        FROM meal_items mi
        LEFT JOIN taco_foods tf ON tf.id = mi.taco_food_id
        WHERE mi.meal_id = ?
        ORDER BY mi.id ASC
        """,
        (row["id"],),
    ).fetchall()

    items = [
        {
            "id": ir["id"],
            "taco_food_id": ir["taco_food_id"],
            "label": ir["label"],
            "grams": ir["grams"],
            "kcal": ir["kcal"],
            "protein_g": ir["protein_g"],
            "carbs_g": ir["carbs_g"],
            "fat_g": ir["fat_g"],
            "fiber_g": ir["fiber_g"],
            "per_100g": {
                "kcal": ir["per_100g_kcal"],
                "protein_g": ir["per_100g_protein"],
                "carbs_g": ir["per_100g_carbs"],
                "fat_g": ir["per_100g_fat"],
                "fiber_g": ir["per_100g_fiber"],
            },
            "confidence": ir["confidence"],
            "source": ir["source"],
            "household_unit_label": ir["household_unit_label"],
            "household_unit_grams": ir["household_unit_grams"],
        }
        for ir in item_rows
    ]

    return {
        "id": row["id"],
        "eaten_date": row["eaten_date"],
        "eaten_time": row["eaten_time"],
        "meal_type": row["meal_type"],
        "title": row["title"],
        "photo_filename": row["photo_filename"],
        "photo_url": f"/api/uploads/{row['photo_filename']}" if row["photo_filename"] else None,
        "notes": row["notes"],
        "ai_provider_used": row["ai_provider_used"],
        "ai_model_used": row["ai_model_used"],
        "overall_confidence": row["overall_confidence"],
        "warnings": json.loads(row["warnings_json"] or "[]"),
        "total_kcal": row["total_kcal"],
        "total_kcal_min": row["total_kcal_min"],
        "total_kcal_max": row["total_kcal_max"],
        "total_protein_g": row["total_protein_g"],
        "total_carbs_g": row["total_carbs_g"],
        "total_fat_g": row["total_fat_g"],
        "total_fiber_g": row["total_fiber_g"],
        "is_favorite": bool(row["is_favorite"]),
        "created_at": row["created_at"],
        "items": items,
    }


def _insert_meal_items(
    conn: sqlite3.Connection,
    meal_id: int,
    items: list[MealItemDraft],
) -> None:
    for item in items:
        conn.execute(
            """
            INSERT INTO meal_items (
                meal_id, taco_food_id, label, grams,
                kcal, protein_g, carbs_g, fat_g, fiber_g,
                per_100g_kcal, per_100g_protein, per_100g_carbs,
                per_100g_fat, per_100g_fiber, confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meal_id,
                item.taco_food_id,
                item.label,
                item.grams,
                item.kcal,
                item.protein_g,
                item.carbs_g,
                item.fat_g,
                item.fiber_g,
                item.per_100g.kcal,
                item.per_100g.protein_g,
                item.per_100g.carbs_g,
                item.per_100g.fat_g,
                item.per_100g.fiber_g,
                item.confidence,
                item.source,
            ),
        )


def _cleanup_orphan_photo(conn: sqlite3.Connection, filename: Optional[str]) -> None:
    if not filename:
        return
    count = conn.execute(
        "SELECT COUNT(*) FROM meal_entries WHERE photo_filename = ?",
        (filename,),
    ).fetchone()[0]
    if count == 0:
        settings = get_settings()
        try:
            path = resolve_safe_upload_path(filename, settings)
            if path.exists():
                path.unlink()
        except InvalidImageError:
            pass


@router.post("/meals/analyze", response_model=AnalyzeMealResponse)
async def analyze_plate_photo(
    file: UploadFile = File(...),
    meal_context: str = Form(default=""),
    plate_size: Literal["pequeno", "normal", "grande"] = Form(default="normal"),
    model_mode: ModelMode = Form(default="precise"),
):
    settings = get_settings()
    raw_bytes = await file.read()

    try:
        photo_filename, jpeg_bytes = process_and_save_plate_image(raw_bytes, settings)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with get_connection(settings) as conn:
        ai_cfg = get_effective_ai_config(conn, settings)
        taco_names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM taco_foods ORDER BY is_custom DESC, name ASC LIMIT 250"
            ).fetchall()
        ]

    try:
        provider = build_vision_provider(ai_cfg)
        analysis = await provider.analyze_plate(
            image_bytes=jpeg_bytes,
            user_context=meal_context,
            plate_size=plate_size,
            model_mode=model_mode,
            taco_names=taco_names,
        )
    except VisionNotConfiguredError as exc:
        saved_path = settings.uploads_dir / photo_filename
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(
            status_code=428,
            detail={"code": "API_KEY_REQUIRED", "message": str(exc)},
        ) from exc
    except VisionProviderError as exc:
        saved_path = settings.uploads_dir / photo_filename
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    draft_items: list[MealItemDraft] = []
    with get_connection(settings) as conn:
        for det in analysis.items:
            taco_match = match_taco_food(conn, det.search_query, det.name)
            if taco_match is not None:
                per_100g = Per100gSchema(
                    kcal=taco_match["kcal_per_100g"],
                    protein_g=taco_match["protein_g"],
                    carbs_g=taco_match["carbs_g"],
                    fat_g=taco_match["fat_g"],
                    fiber_g=taco_match["fiber_g"],
                )
                taco_id = taco_match["id"]
                label = taco_match["name"]
                source: Literal["taco", "ai_fallback", "manual"] = "taco"
                unit_label = taco_match["household_unit_label"]
                unit_grams = taco_match["household_unit_grams"]
            else:
                per_100g = det.fallback_per_100g
                taco_id = None
                label = det.name
                source = "ai_fallback"
                unit_label = None
                unit_grams = None

            macros = calculate_item_macros(per_100g, det.estimated_grams)
            draft_items.append(
                MealItemDraft(
                    taco_food_id=taco_id,
                    label=label,
                    grams=round(det.estimated_grams, 1),
                    kcal=macros["kcal"],
                    protein_g=macros["protein_g"],
                    carbs_g=macros["carbs_g"],
                    fat_g=macros["fat_g"],
                    fiber_g=macros["fiber_g"],
                    per_100g=per_100g,
                    confidence=round(det.confidence, 2),
                    source=source,
                    portion_label=det.portion_label,
                    household_unit_label=unit_label,
                    household_unit_grams=unit_grams,
                )
            )

    totals: MealTotals = compute_meal_totals(draft_items)
    return AnalyzeMealResponse(
        plate_summary=analysis.plate_summary,
        photo_filename=photo_filename,
        ai_provider_used=analysis.provider_used,
        ai_model_used=analysis.model_used,
        used_fallback_model=analysis.used_fallback_model,
        warnings=analysis.warnings,
        items=draft_items,
        totals=totals,
    )


@router.post("/meals/recalculate", response_model=RecalculateResponse)
def recalculate_meal(payload: RecalculateRequest):
    settings = get_settings()
    with get_connection(settings) as conn:
        try:
            items, totals = resolve_and_calculate_items(conn, payload.items)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecalculateResponse(items=items, totals=totals)


@router.post("/meals", status_code=201)
def create_meal(payload: CreateMealRequest):
    settings = get_settings()
    if payload.photo_filename:
        try:
            path = resolve_safe_upload_path(payload.photo_filename, settings)
            if not path.exists():
                raise HTTPException(status_code=400, detail="Foto referenciada não encontrada.")
        except InvalidImageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    with get_connection(settings) as conn:
        try:
            items, totals = resolve_and_calculate_items(conn, payload.items)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        now = utc_now_iso()
        cursor = conn.execute(
            """
            INSERT INTO meal_entries (
                eaten_date, eaten_time, meal_type, title, photo_filename, notes,
                ai_provider_used, ai_model_used, overall_confidence, warnings_json,
                total_kcal, total_kcal_min, total_kcal_max,
                total_protein_g, total_carbs_g, total_fat_g, total_fiber_g,
                is_favorite, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.eaten_date,
                payload.eaten_time,
                payload.meal_type,
                payload.title.strip(),
                payload.photo_filename,
                payload.notes.strip(),
                payload.ai_provider_used,
                payload.ai_model_used,
                totals.overall_confidence,
                json.dumps(payload.warnings, ensure_ascii=False),
                totals.total_kcal,
                totals.total_kcal_min,
                totals.total_kcal_max,
                totals.total_protein_g,
                totals.total_carbs_g,
                totals.total_fat_g,
                totals.total_fiber_g,
                1 if payload.is_favorite else 0,
                now,
            ),
        )
        meal_id = cursor.lastrowid
        _insert_meal_items(conn, meal_id, items)
        row = conn.execute("SELECT * FROM meal_entries WHERE id = ?", (meal_id,)).fetchone()
        return _serialize_meal_row(conn, row)


@router.get("/meals")
def list_meals_by_date(
    date_str: str = Query(alias="date", default="", max_length=10),
):
    target_date = date_str or date.today().isoformat()
    settings = get_settings()
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT * FROM meal_entries
            WHERE eaten_date = ?
            ORDER BY eaten_time DESC, id DESC
            """,
            (target_date,),
        ).fetchall()
        meals = [_serialize_meal_row(conn, r) for r in rows]
        goals_row = conn.execute("SELECT * FROM user_profile_goals WHERE id = 1").fetchone()

        day_totals = {
            "kcal": round(sum(m["total_kcal"] for m in meals), 1),
            "kcal_min": round(sum(m["total_kcal_min"] for m in meals), 0),
            "kcal_max": round(sum(m["total_kcal_max"] for m in meals), 0),
            "protein_g": round(sum(m["total_protein_g"] for m in meals), 1),
            "carbs_g": round(sum(m["total_carbs_g"] for m in meals), 1),
            "fat_g": round(sum(m["total_fat_g"] for m in meals), 1),
            "fiber_g": round(sum(m["total_fiber_g"] for m in meals), 1),
        }
        return {
            "date": target_date,
            "meals": meals,
            "day_totals": day_totals,
            "goals": dict(goals_row),
        }


@router.get("/meals/favorites")
def list_favorite_meals():
    settings = get_settings()
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT * FROM meal_entries
            WHERE is_favorite = 1
            ORDER BY id DESC
            LIMIT 25
            """
        ).fetchall()
        if not rows:
            # Retorna também as últimas refeições únicas como atalho rápido
            rows = conn.execute(
                """
                SELECT * FROM meal_entries
                ORDER BY id DESC
                LIMIT 10
                """
            ).fetchall()
        return [_serialize_meal_row(conn, r) for r in rows]


@router.post("/meals/{meal_id}/repeat", status_code=201)
def repeat_meal(
    meal_id: int,
    eaten_date: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    meal_type: Optional[Literal["cafe", "almoco", "jantar", "lanche"]] = Query(default=None),
):
    settings = get_settings()
    with get_connection(settings) as conn:
        orig = conn.execute("SELECT * FROM meal_entries WHERE id = ?", (meal_id,)).fetchone()
        if orig is None:
            raise HTTPException(status_code=404, detail="Refeição não encontrada.")

        target_date = eaten_date or date.today().isoformat()
        target_time = datetime.now().strftime("%H:%M")
        target_type = meal_type or orig["meal_type"]
        now = utc_now_iso()

        cursor = conn.execute(
            """
            INSERT INTO meal_entries (
                eaten_date, eaten_time, meal_type, title, photo_filename, notes,
                ai_provider_used, ai_model_used, overall_confidence, warnings_json,
                total_kcal, total_kcal_min, total_kcal_max,
                total_protein_g, total_carbs_g, total_fat_g, total_fiber_g,
                is_favorite, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                target_date,
                target_time,
                target_type,
                orig["title"],
                orig["photo_filename"],
                orig["notes"],
                orig["ai_provider_used"],
                orig["ai_model_used"],
                orig["overall_confidence"],
                orig["warnings_json"],
                orig["total_kcal"],
                orig["total_kcal_min"],
                orig["total_kcal_max"],
                orig["total_protein_g"],
                orig["total_carbs_g"],
                orig["total_fat_g"],
                orig["total_fiber_g"],
                now,
            ),
        )
        new_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO meal_items (
                meal_id, taco_food_id, label, grams,
                kcal, protein_g, carbs_g, fat_g, fiber_g,
                per_100g_kcal, per_100g_protein, per_100g_carbs,
                per_100g_fat, per_100g_fiber, confidence, source
            )
            SELECT ?, taco_food_id, label, grams,
                   kcal, protein_g, carbs_g, fat_g, fiber_g,
                   per_100g_kcal, per_100g_protein, per_100g_carbs,
                   per_100g_fat, per_100g_fiber, confidence, source
            FROM meal_items
            WHERE meal_id = ?
            ORDER BY id ASC
            """,
            (new_id, meal_id),
        )
        created = conn.execute("SELECT * FROM meal_entries WHERE id = ?", (new_id,)).fetchone()
        return _serialize_meal_row(conn, created)


@router.patch("/meals/{meal_id}")
def update_meal(meal_id: int, payload: UpdateMealRequest):
    settings = get_settings()
    with get_connection(settings) as conn:
        existing = conn.execute("SELECT * FROM meal_entries WHERE id = ?", (meal_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Refeição não encontrada.")

        new_type = payload.meal_type if payload.meal_type is not None else existing["meal_type"]
        new_title = payload.title.strip() if payload.title is not None else existing["title"]
        new_notes = payload.notes.strip() if payload.notes is not None else existing["notes"]
        new_fav = (1 if payload.is_favorite else 0) if payload.is_favorite is not None else existing["is_favorite"]

        if payload.items is not None:
            if not payload.items:
                raise HTTPException(status_code=400, detail="A refeição deve conter ao menos um item.")
            items, totals = resolve_and_calculate_items(conn, payload.items)
            conn.execute("DELETE FROM meal_items WHERE meal_id = ?", (meal_id,))
            _insert_meal_items(conn, meal_id, items)
            conn.execute(
                """
                UPDATE meal_entries
                SET meal_type = ?, title = ?, notes = ?, is_favorite = ?,
                    overall_confidence = ?, total_kcal = ?, total_kcal_min = ?, total_kcal_max = ?,
                    total_protein_g = ?, total_carbs_g = ?, total_fat_g = ?, total_fiber_g = ?
                WHERE id = ?
                """,
                (
                    new_type,
                    new_title,
                    new_notes,
                    new_fav,
                    totals.overall_confidence,
                    totals.total_kcal,
                    totals.total_kcal_min,
                    totals.total_kcal_max,
                    totals.total_protein_g,
                    totals.total_carbs_g,
                    totals.total_fat_g,
                    totals.total_fiber_g,
                    meal_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE meal_entries
                SET meal_type = ?, title = ?, notes = ?, is_favorite = ?
                WHERE id = ?
                """,
                (new_type, new_title, new_notes, new_fav, meal_id),
            )

        updated = conn.execute("SELECT * FROM meal_entries WHERE id = ?", (meal_id,)).fetchone()
        return _serialize_meal_row(conn, updated)


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: int):
    settings = get_settings()
    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT photo_filename FROM meal_entries WHERE id = ?",
            (meal_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Refeição não encontrada.")
        photo_filename = existing["photo_filename"]
        conn.execute("DELETE FROM meal_entries WHERE id = ?", (meal_id,))
        _cleanup_orphan_photo(conn, photo_filename)
    return {"deleted": True, "id": meal_id}


@router.get("/stats/summary")
def get_stats_summary(days: int = Query(default=7, ge=1, le=90)):
    settings = get_settings()
    end_day = date.today()
    start_day = end_day - timedelta(days=days - 1)
    start_iso = start_day.isoformat()
    end_iso = end_day.isoformat()

    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT
                eaten_date,
                COUNT(*) AS meal_count,
                ROUND(SUM(total_kcal), 1) AS kcal,
                ROUND(SUM(total_protein_g), 1) AS protein_g,
                ROUND(SUM(total_carbs_g), 1) AS carbs_g,
                ROUND(SUM(total_fat_g), 1) AS fat_g,
                ROUND(SUM(total_fiber_g), 1) AS fiber_g
            FROM meal_entries
            WHERE eaten_date BETWEEN ? AND ?
            GROUP BY eaten_date
            ORDER BY eaten_date ASC
            """,
            (start_iso, end_iso),
        ).fetchall()
        water_rows = conn.execute(
            """
            SELECT log_date, SUM(amount_ml) AS water_ml
            FROM water_logs
            WHERE log_date BETWEEN ? AND ?
            GROUP BY log_date
            """,
            (start_iso, end_iso),
        ).fetchall()
        goals = dict(conn.execute("SELECT * FROM user_profile_goals WHERE id = 1").fetchone())

    by_date = {r["eaten_date"]: dict(r) for r in rows}
    water_by_date = {r["log_date"]: int(r["water_ml"] or 0) for r in water_rows}
    series = []
    for offset in range(days):
        d = (start_day + timedelta(days=offset)).isoformat()
        entry = by_date.get(d)
        series.append(
            {
                "date": d,
                "label": f"{d[8:10]}/{d[5:7]}",
                "meal_count": entry["meal_count"] if entry else 0,
                "kcal": entry["kcal"] if entry else 0.0,
                "protein_g": entry["protein_g"] if entry else 0.0,
                "carbs_g": entry["carbs_g"] if entry else 0.0,
                "fat_g": entry["fat_g"] if entry else 0.0,
                "fiber_g": entry["fiber_g"] if entry else 0.0,
                "water_ml": water_by_date.get(d, 0),
                "goal_kcal": goals["daily_kcal_goal"],
            }
        )

    logged_days = [s for s in series if s["meal_count"] > 0]
    water_days = [s for s in series if s["water_ml"] > 0]
    divisor = len(logged_days) or 1
    averages = {
        "logged_days": len(logged_days),
        "avg_kcal": round(sum(s["kcal"] for s in logged_days) / divisor, 1) if logged_days else 0.0,
        "avg_protein_g": round(sum(s["protein_g"] for s in logged_days) / divisor, 1) if logged_days else 0.0,
        "avg_carbs_g": round(sum(s["carbs_g"] for s in logged_days) / divisor, 1) if logged_days else 0.0,
        "avg_fat_g": round(sum(s["fat_g"] for s in logged_days) / divisor, 1) if logged_days else 0.0,
        "avg_water_ml": round(sum(s["water_ml"] for s in water_days) / len(water_days), 0) if water_days else 0.0,
    }
    return {"days": days, "series": series, "averages": averages, "goals": goals}


@router.get("/uploads/{filename}")
def get_uploaded_photo(filename: str):
    settings = get_settings()
    try:
        path = resolve_safe_upload_path(filename, settings)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return FileResponse(path, media_type="image/jpeg")
