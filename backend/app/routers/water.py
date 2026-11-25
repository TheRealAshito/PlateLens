"""Endpoints do tracker diário de água (hidratação)."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.config import get_settings
from backend.app.database import get_connection, utc_now_iso
from backend.app.schemas import (
    WaterDayResponse,
    WaterEntryCreate,
    WaterEntryResponse,
)

router = APIRouter(prefix="/api/water", tags=["water"])


@router.get("", response_model=WaterDayResponse)
def get_water_day(date_str: str = Query(alias="date", default="", max_length=10)):
    target_date = date_str or date.today().isoformat()
    settings = get_settings()
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT * FROM water_logs
            WHERE log_date = ?
            ORDER BY log_time DESC, id DESC
            """,
            (target_date,),
        ).fetchall()
        goals = conn.execute("SELECT water_goal_ml FROM user_profile_goals WHERE id = 1").fetchone()
        goal_ml = int(goals["water_goal_ml"]) if goals else 2500
        entries = [WaterEntryResponse(**dict(r)) for r in rows]
        total_ml = sum(e.amount_ml for e in entries)
        return WaterDayResponse(
            date=target_date,
            total_ml=total_ml,
            goal_ml=goal_ml,
            entries=entries,
        )


@router.post("", response_model=WaterEntryResponse, status_code=201)
def add_water_entry(payload: WaterEntryCreate):
    settings = get_settings()
    now = utc_now_iso()
    with get_connection(settings) as conn:
        cursor = conn.execute(
            """
            INSERT INTO water_logs (log_date, log_time, amount_ml, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.log_date,
                payload.log_time,
                payload.amount_ml,
                payload.note.strip(),
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM water_logs WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return WaterEntryResponse(**dict(row))


@router.delete("/{entry_id}")
def delete_water_entry(entry_id: int):
    settings = get_settings()
    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT id FROM water_logs WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Registro de água não encontrado.")
        conn.execute("DELETE FROM water_logs WHERE id = ?", (entry_id,))
    return {"deleted": True, "id": entry_id}
