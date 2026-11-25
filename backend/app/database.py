"""Camada de banco de dados SQLite (WAL) e carga inicial da Tabela TACO."""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from backend.app.config import Settings, ensure_directories, get_settings

TACO_SEED_PATH = Path(__file__).resolve().parent / "data" / "taco_seed.json"


def normalize_text(text: str) -> str:
    """Remove acentos, converte para minúsculas e normaliza espaços."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in stripped.lower())
    return " ".join(cleaned.split())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    """Abre conexão SQLite configurada com WAL e foreign keys."""
    cfg = ensure_directories(settings or get_settings())
    conn = sqlite3.connect(str(cfg.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(settings: Settings | None = None) -> None:
    """Cria tabelas caso não existam e popula a Tabela TACO + meta padrão."""
    cfg = ensure_directories(settings or get_settings())
    with get_connection(cfg) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_profile_goals (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                sex TEXT NOT NULL DEFAULT 'M',
                age INTEGER NOT NULL DEFAULT 30,
                weight_kg REAL NOT NULL DEFAULT 75.0,
                height_cm REAL NOT NULL DEFAULT 175.0,
                activity_level TEXT NOT NULL DEFAULT 'moderate',
                goal_mode TEXT NOT NULL DEFAULT 'lose',
                daily_kcal_goal REAL NOT NULL DEFAULT 2000.0,
                protein_goal_g REAL NOT NULL DEFAULT 140.0,
                carbs_goal_g REAL NOT NULL DEFAULT 215.0,
                fat_goal_g REAL NOT NULL DEFAULT 62.0,
                fiber_goal_g REAL NOT NULL DEFAULT 28.0,
                water_goal_ml INTEGER NOT NULL DEFAULT 2500,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS taco_foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                name_normalized TEXT NOT NULL,
                category TEXT NOT NULL,
                kcal_per_100g REAL NOT NULL,
                protein_g REAL NOT NULL,
                carbs_g REAL NOT NULL,
                fat_g REAL NOT NULL,
                fiber_g REAL NOT NULL DEFAULT 0.0,
                household_unit_label TEXT NOT NULL DEFAULT '1 porção',
                household_unit_grams REAL NOT NULL DEFAULT 100.0,
                is_custom INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_taco_name_norm
                ON taco_foods (name_normalized);

            CREATE TABLE IF NOT EXISTS meal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eaten_date TEXT NOT NULL,
                eaten_time TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                photo_filename TEXT,
                notes TEXT NOT NULL DEFAULT '',
                ai_provider_used TEXT NOT NULL DEFAULT 'manual',
                ai_model_used TEXT NOT NULL DEFAULT '',
                overall_confidence TEXT NOT NULL DEFAULT 'high',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                total_kcal REAL NOT NULL,
                total_kcal_min REAL NOT NULL,
                total_kcal_max REAL NOT NULL,
                total_protein_g REAL NOT NULL,
                total_carbs_g REAL NOT NULL,
                total_fat_g REAL NOT NULL,
                total_fiber_g REAL NOT NULL,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_meal_entries_date
                ON meal_entries (eaten_date, eaten_time);

            CREATE TABLE IF NOT EXISTS meal_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL REFERENCES meal_entries(id) ON DELETE CASCADE,
                taco_food_id INTEGER REFERENCES taco_foods(id) ON DELETE SET NULL,
                label TEXT NOT NULL,
                grams REAL NOT NULL,
                kcal REAL NOT NULL,
                protein_g REAL NOT NULL,
                carbs_g REAL NOT NULL,
                fat_g REAL NOT NULL,
                fiber_g REAL NOT NULL,
                per_100g_kcal REAL NOT NULL,
                per_100g_protein REAL NOT NULL,
                per_100g_carbs REAL NOT NULL,
                per_100g_fat REAL NOT NULL,
                per_100g_fiber REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'taco'
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS water_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT NOT NULL,
                log_time TEXT NOT NULL,
                amount_ml INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_water_logs_date
                ON water_logs (log_date, log_time);
            """
        )

        # Migração segura para bancos existentes sem water_goal_ml
        goal_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(user_profile_goals)").fetchall()
        }
        if "water_goal_ml" not in goal_cols:
            conn.execute(
                "ALTER TABLE user_profile_goals ADD COLUMN water_goal_ml INTEGER NOT NULL DEFAULT 2500"
            )

        # Garante meta padrão inicial
        now = utc_now_iso()
        conn.execute(
            """
            INSERT OR IGNORE INTO user_profile_goals (id, updated_at)
            VALUES (1, ?)
            """,
            (now,),
        )

        # Popula Tabela TACO inicial de forma idempotente
        if TACO_SEED_PATH.exists():
            seed_items = json.loads(TACO_SEED_PATH.read_text(encoding="utf-8"))
            for item in seed_items:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO taco_foods (
                        name, name_normalized, category,
                        kcal_per_100g, protein_g, carbs_g, fat_g, fiber_g,
                        household_unit_label, household_unit_grams, is_custom
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        item["name"],
                        normalize_text(item["name"]),
                        item["category"],
                        float(item["kcal_per_100g"]),
                        float(item["protein_g"]),
                        float(item["carbs_g"]),
                        float(item["fat_g"]),
                        float(item.get("fiber_g", 0.0)),
                        item.get("household_unit_label", "1 porção"),
                        float(item.get("household_unit_grams", 100.0)),
                    ),
                )
