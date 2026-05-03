import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


def _resolve_db_url() -> str:
    db_url = settings.DATABASE_URL
    return db_url


def _column_exists(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _run_migration(db_url: str, label: str):
    engine = create_engine(db_url, connect_args={"init_command": "SET sql_mode='NO_ENGINE_SUBSTITUTION'"})
    try:
        with engine.connect() as conn:
            if _column_exists(engine, "test_cases", "prior_quality_score"):
                print(f"[{label}] prior_quality_score 列已存在，跳过")
                return
            conn.execute(text(
                "ALTER TABLE test_cases ADD COLUMN prior_quality_score FLOAT NULL "
                "COMMENT 'prior quality score 0-100 computed by QualityGate'"
            ))
            conn.commit()
            print(f"[{label}] prior_quality_score 列已添加")
    finally:
        engine.dispose()


def main():
    main_url = _resolve_db_url()
    _run_migration(main_url, "main")

    test_url = main_url.replace("/ai_testmaster", "/ai_testmaster_test") if "/ai_testmaster" in main_url else None
    if test_url:
        _run_migration(test_url, "test")


if __name__ == "__main__":
    main()
