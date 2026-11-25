"""Endpoints de metas diárias e calculadora educativa TMB/TDEE."""

from fastapi import APIRouter

from backend.app.config import get_settings
from backend.app.database import get_connection, utc_now_iso
from backend.app.schemas import (
    GoalsResponse,
    TdeeCalculateRequest,
    TdeeCalculateResponse,
    UpdateGoalsRequest,
)
from backend.app.services.nutrition_engine import calculate_tdee_plan

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=GoalsResponse)
def get_goals():
    settings = get_settings()
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM user_profile_goals WHERE id = 1").fetchone()
        return GoalsResponse(**dict(row))


@router.put("", response_model=GoalsResponse)
def update_goals(payload: UpdateGoalsRequest):
    settings = get_settings()
    now = utc_now_iso()
    with get_connection(settings) as conn:
        conn.execute(
            """
            UPDATE user_profile_goals
            SET sex = ?, age = ?, weight_kg = ?, height_cm = ?,
                activity_level = ?, goal_mode = ?,
                daily_kcal_goal = ?, protein_goal_g = ?,
                carbs_goal_g = ?, fat_goal_g = ?, fiber_goal_g = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                payload.sex,
                payload.age,
                payload.weight_kg,
                payload.height_cm,
                payload.activity_level,
                payload.goal_mode,
                payload.daily_kcal_goal,
                payload.protein_goal_g,
                payload.carbs_goal_g,
                payload.fat_goal_g,
                payload.fiber_goal_g,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM user_profile_goals WHERE id = 1").fetchone()
        return GoalsResponse(**dict(row))


@router.post("/calculate-tdee", response_model=TdeeCalculateResponse)
def calculate_tdee(payload: TdeeCalculateRequest):
    return calculate_tdee_plan(
        sex=payload.sex,
        age=payload.age,
        weight_kg=payload.weight_kg,
        height_cm=payload.height_cm,
        activity_level=payload.activity_level,
        goal_mode=payload.goal_mode,
    )
