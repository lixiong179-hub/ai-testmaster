from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


MERGED_REVISION = "20260423_merge_heads"
KNOWN_ORPHAN_REVISIONS = {"d6e7f8a9b0c1"}


@dataclass(frozen=True)
class RepairStep:
    description: str
    sql: str


def get_current_revisions(connection) -> list[str]:
    rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return [row[0] for row in rows]


def has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def has_unique(inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def has_foreign_key(inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        foreign_key["name"] == constraint_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def ensure_required_columns(inspector) -> None:
    required_columns = {
        "test_points": {"created_by"},
        "test_cases": {"test_point_id", "test_category"},
        "project_files": {"resource_type"},
        "test_steps": {
            "is_business_view",
            "is_technical_view",
            "has_locator",
            "locator_status",
        },
        "element_locators": {"precondition_step_id", "step_id"},
    }
    for table_name, expected_columns in required_columns.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            raise RuntimeError(
                f"表 {table_name} 缺少字段: {', '.join(sorted(missing_columns))}"
            )
    if not inspector.has_table("test_case_precondition_steps"):
        raise RuntimeError("缺少表 test_case_precondition_steps")


def ensure_unique_precondition_for_step_ids(connection) -> None:
    duplicate_rows = connection.execute(
        text(
            """
            SELECT step_id, COUNT(*) AS row_count
            FROM element_locators
            WHERE step_id IS NOT NULL
            GROUP BY step_id
            HAVING COUNT(*) > 1
            LIMIT 20
            """
        )
    ).fetchall()
    if duplicate_rows:
        raise RuntimeError(
            f"element_locators.step_id 存在重复值，无法安全补唯一约束: {duplicate_rows}"
        )


def collect_repair_steps(connection, inspector) -> list[RepairStep]:
    ensure_required_columns(inspector)
    ensure_unique_precondition_for_step_ids(connection)

    steps: list[RepairStep] = []

    if not has_unique(inspector, "element_locators", "uq_element_locators_step_id"):
        steps.append(
            RepairStep(
                description="为 element_locators.step_id 补唯一约束",
                sql=(
                    "ALTER TABLE element_locators "
                    "ADD CONSTRAINT uq_element_locators_step_id UNIQUE (step_id)"
                ),
            )
        )

    if not has_index(inspector, "element_locators", "ix_element_locators_precondition_step_id"):
        steps.append(
            RepairStep(
                description="为 element_locators.precondition_step_id 补索引",
                sql=(
                    "CREATE INDEX ix_element_locators_precondition_step_id "
                    "ON element_locators (precondition_step_id)"
                ),
            )
        )

    if not has_foreign_key(
        inspector,
        "element_locators",
        "fk_element_locators_precondition_step_id",
    ):
        steps.append(
            RepairStep(
                description="为 element_locators.precondition_step_id 补外键",
                sql=(
                    "ALTER TABLE element_locators "
                    "ADD CONSTRAINT fk_element_locators_precondition_step_id "
                    "FOREIGN KEY (precondition_step_id) "
                    "REFERENCES test_case_precondition_steps (id) "
                    "ON DELETE CASCADE"
                ),
            )
        )

    if not has_index(inspector, "test_cases", "ix_test_cases_test_point_id"):
        steps.append(
            RepairStep(
                description="为 test_cases.test_point_id 补索引",
                sql=(
                    "CREATE INDEX ix_test_cases_test_point_id "
                    "ON test_cases (test_point_id)"
                ),
            )
        )

    if not has_foreign_key(inspector, "test_cases", "fk_test_cases_test_point_id"):
        steps.append(
            RepairStep(
                description="为 test_cases.test_point_id 补外键",
                sql=(
                    "ALTER TABLE test_cases "
                    "ADD CONSTRAINT fk_test_cases_test_point_id "
                    "FOREIGN KEY (test_point_id) "
                    "REFERENCES test_points (id) "
                    "ON DELETE SET NULL"
                ),
            )
        )

    return steps


def print_steps(steps: Iterable[RepairStep]) -> None:
    for step in steps:
        print(f"- {step.description}")
        print(f"  SQL: {step.sql}")


def rewrite_alembic_version(connection) -> None:
    connection.execute(text("DELETE FROM alembic_version"))
    connection.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
        {"version_num": MERGED_REVISION},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="修复本地数据库 Alembic 历史断层")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行修复；默认仅做检查和打印计划",
    )
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.begin() as connection:
            current_revisions = get_current_revisions(connection)
            inspector = inspect(connection)
            repair_steps = collect_repair_steps(connection, inspector)

            print(f"当前 alembic_version: {current_revisions}")
            if any(revision in KNOWN_ORPHAN_REVISIONS for revision in current_revisions):
                print("检测到已知孤儿 revision，允许修复并重写到合并后的 head。")
            else:
                print("未检测到已知孤儿 revision，将只做结构补齐和 head 归一化。")

            if repair_steps:
                print("待执行修复步骤:")
                print_steps(repair_steps)
            else:
                print("未发现缺失约束或索引。")

            print(f"目标版本将设置为: {MERGED_REVISION}")

            if not args.apply:
                print("Dry run 完成，未修改数据库。")
                return 0

            for step in repair_steps:
                print(f"执行: {step.description}")
                connection.execute(text(step.sql))

            rewrite_alembic_version(connection)
            print("已重写 alembic_version。")
            print("修复完成。")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
