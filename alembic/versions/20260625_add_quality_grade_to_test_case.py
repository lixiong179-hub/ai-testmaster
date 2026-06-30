"""add quality_grade to test_cases

Revision ID: 20260625_add_quality_grade
Revises: c9d0e1f2a3b4
Create Date: 2026-06-25

新增1个质量等级字段：
    - quality_grade: A/B/C/D 质量等级，由 prior_quality_score 映射
      映射规则: A>=85 / B>=65 / C>=45 / D<45

回滚策略: drop_column，nullable=True 保证回滚不丢失历史数据兼容性。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_add_quality_grade"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 quality_grade 字段到 test_cases 表，并回填历史数据。

    回填原因：历史用例已有 prior_quality_score 但 quality_grade 为 NULL，
    下游按等级过滤/统计会漏掉这些用例。回填规则与 score_to_grade 保持一致：
        A>=85 / B>=65 / C>=45 / D<45
    仅回填 prior_quality_score IS NOT NULL 的行，未评分用例保持 NULL。
    """
    op.add_column(
        "test_cases",
        sa.Column(
            "quality_grade",
            sa.String(2),
            nullable=True,
            comment="A/B/C/D 质量等级，由 prior_quality_score 映射：A>=85/B>=65/C>=45/D<45",
        ),
    )
    # 回填历史数据：使用参数化 SQL 避免注入风险，CASE 表达式与 score_to_grade 对齐
    op.execute(
        sa.text(
            """
            UPDATE test_cases
            SET quality_grade = CASE
                WHEN prior_quality_score >= 85 THEN 'A'
                WHEN prior_quality_score >= 65 THEN 'B'
                WHEN prior_quality_score >= 45 THEN 'C'
                ELSE 'D'
            END
            WHERE prior_quality_score IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    """删除 quality_grade 字段。"""
    op.drop_column("test_cases", "quality_grade")
