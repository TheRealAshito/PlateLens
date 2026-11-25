"""Schemas Pydantic compartilhados da API do PlateLens."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


MealType = Literal["cafe", "almoco", "jantar", "lanche"]
SexType = Literal["M", "F"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
GoalMode = Literal["lose", "maintain", "gain"]
ModelMode = Literal["precise", "lite"]


class Per100gSchema(BaseModel):
    kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float = Field(default=0.0, ge=0)


class MealItemDraft(BaseModel):
    taco_food_id: Optional[int] = None
    label: str = Field(min_length=1, max_length=160)
    grams: float = Field(gt=0, le=5000)
    kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    per_100g: Per100gSchema
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Literal["taco", "ai_fallback", "manual"] = "taco"
    portion_label: Optional[str] = None
    household_unit_label: Optional[str] = None
    household_unit_grams: Optional[float] = None


class RecalculateItemInput(BaseModel):
    taco_food_id: Optional[int] = None
    label: str = Field(min_length=1, max_length=160)
    grams: float = Field(gt=0, le=5000)
    per_100g: Optional[Per100gSchema] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Literal["taco", "ai_fallback", "manual"] = "taco"


class RecalculateRequest(BaseModel):
    items: list[RecalculateItemInput] = Field(min_length=1)


class MealTotals(BaseModel):
    total_kcal: float
    total_kcal_min: float
    total_kcal_max: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_fiber_g: float
    overall_confidence: Literal["high", "medium", "low"]


class AnalyzeMealResponse(BaseModel):
    plate_summary: str
    photo_filename: str
    ai_provider_used: str
    ai_model_used: str
    used_fallback_model: bool = False
    warnings: list[str] = Field(default_factory=list)
    items: list[MealItemDraft]
    totals: MealTotals


class RecalculateResponse(BaseModel):
    items: list[MealItemDraft]
    totals: MealTotals


class CreateMealRequest(BaseModel):
    eaten_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    eaten_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    meal_type: MealType
    title: str = Field(min_length=1, max_length=160)
    photo_filename: Optional[str] = None
    notes: str = Field(default="", max_length=1000)
    ai_provider_used: str = Field(default="manual", max_length=60)
    ai_model_used: str = Field(default="", max_length=100)
    warnings: list[str] = Field(default_factory=list)
    is_favorite: bool = False
    items: list[RecalculateItemInput] = Field(min_length=1)


class UpdateMealRequest(BaseModel):
    meal_type: Optional[MealType] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=1000)
    is_favorite: Optional[bool] = None
    items: Optional[list[RecalculateItemInput]] = None


class TacoFoodResponse(BaseModel):
    id: int
    name: str
    category: str
    kcal_per_100g: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    household_unit_label: str
    household_unit_grams: float
    is_custom: bool = False


class CreateCustomFoodRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="Personalizados", min_length=2, max_length=60)
    kcal_per_100g: float = Field(ge=0, le=950)
    protein_g: float = Field(ge=0, le=100)
    carbs_g: float = Field(ge=0, le=100)
    fat_g: float = Field(ge=0, le=100)
    fiber_g: float = Field(default=0.0, ge=0, le=100)
    household_unit_label: str = Field(default="1 porção", min_length=1, max_length=60)
    household_unit_grams: float = Field(default=100.0, gt=0, le=2000)


class GoalsResponse(BaseModel):
    sex: SexType
    age: int
    weight_kg: float
    height_cm: float
    activity_level: ActivityLevel
    goal_mode: GoalMode
    daily_kcal_goal: float
    protein_goal_g: float
    carbs_goal_g: float
    fat_goal_g: float
    fiber_goal_g: float
    updated_at: str


class UpdateGoalsRequest(BaseModel):
    sex: SexType = "M"
    age: int = Field(ge=14, le=110)
    weight_kg: float = Field(gt=25, le=350)
    height_cm: float = Field(gt=100, le=250)
    activity_level: ActivityLevel = "moderate"
    goal_mode: GoalMode = "lose"
    daily_kcal_goal: float = Field(ge=1000, le=8000)
    protein_goal_g: float = Field(ge=20, le=500)
    carbs_goal_g: float = Field(ge=0, le=900)
    fat_goal_g: float = Field(ge=10, le=350)
    fiber_goal_g: float = Field(ge=5, le=150)


class TdeeCalculateRequest(BaseModel):
    sex: SexType
    age: int = Field(ge=14, le=110)
    weight_kg: float = Field(gt=25, le=350)
    height_cm: float = Field(gt=100, le=250)
    activity_level: ActivityLevel
    goal_mode: GoalMode


class TdeeCalculateResponse(BaseModel):
    bmr_kcal: float
    tdee_kcal: float
    recommended_kcal: float
    protein_goal_g: float
    carbs_goal_g: float
    fat_goal_g: float
    fiber_goal_g: float
    goal_delta_kcal: float


class AiSettingsStatus(BaseModel):
    vision_provider: str
    ai_configured: bool
    needs_setup: bool
    onboarding_dismissed: bool
    key_source: Literal["env", "database", "none"]
    masked_key: Optional[str] = None
    gemini_model: str
    gemini_fallback_model: str
    ollama_base_url: str
    ollama_model: str


class UpdateAiSettingsRequest(BaseModel):
    vision_provider: Optional[Literal["gemini", "ollama", "disabled"]] = None
    gemini_api_key: Optional[str] = None
    clear_gemini_api_key: bool = False
    gemini_model: Optional[str] = Field(default=None, max_length=100)
    gemini_fallback_model: Optional[str] = Field(default=None, max_length=100)
    ollama_base_url: Optional[str] = Field(default=None, max_length=255)
    ollama_model: Optional[str] = Field(default=None, max_length=100)
    onboarding_dismissed: Optional[bool] = None
