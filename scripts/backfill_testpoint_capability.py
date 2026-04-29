"""回填脚本：为每个 project 创建 default capability，并将所有现有 test_point 关联到它。

幂等设计：重复运行不会重复创建 default capability。

用法：
    python scripts/backfill_testpoint_capability.py --dry-run   # 预览模式，不写入数据库
    python scripts/backfill_testpoint_capability.py             # 执行回填
"""
import argparse
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.database import PrimarySessionLocal, get_db_context
from app.models.test_point import TestPoint
from app.models.test_capability import TestCapability
from app.models.project import Project

DEFAULT_CAPABILITY_KEY = "default"
DEFAULT_CAPABILITY_TITLE = "默认能力"
BATCH_SIZE = 1000


def backfill(dry_run: bool = False) -> None:
    """执行回填逻辑。

    Args:
        dry_run: 如果为 True，只打印将要执行的操作，不实际写入数据库。
    """
    db: Session = PrimarySessionLocal()
    try:
        # 1. 查找所有 project
        projects = db.query(Project).all()
        print(f"找到 {len(projects)} 个项目")

        for project in projects:
            # 2. 检查该项目是否已有 default capability（幂等）
            existing = db.query(TestCapability).filter(
                TestCapability.project_id == project.id,
                TestCapability.key == DEFAULT_CAPABILITY_KEY,
            ).first()

            if existing:
                default_cap = existing
                print(f"  项目 {project.id} ({project.name}): default capability 已存在 (id={default_cap.id})")
            else:
                if dry_run:
                    print(f"  项目 {project.id} ({project.name}): [DRY-RUN] 将创建 default capability")
                    default_cap = None
                else:
                    default_cap = TestCapability(
                        project_id=project.id,
                        key=DEFAULT_CAPABILITY_KEY,
                        title=DEFAULT_CAPABILITY_TITLE,
                        description="自动创建的默认能力，用于关联历史测试点",
                        status="active",
                    )
                    db.add(default_cap)
                    db.flush()
                    print(f"  项目 {project.id} ({project.name}): 创建 default capability (id={default_cap.id})")

            # 3. 查找该项目下 capability_id 为 NULL 的 test_point
            orphan_points = db.query(TestPoint).filter(
                TestPoint.project_id == project.id,
                TestPoint.capability_id.is_(None),
            ).all()

            if not orphan_points:
                print(f"  项目 {project.id}: 无孤立测试点，跳过")
                continue

            print(f"  项目 {project.id}: 发现 {len(orphan_points)} 个孤立测试点")

            if dry_run:
                print(f"  项目 {project.id}: [DRY-RUN] 将关联 {len(orphan_points)} 个测试点到 default capability")
            else:
                # 分批更新，避免大事务
                for i in range(0, len(orphan_points), BATCH_SIZE):
                    batch = orphan_points[i:i + BATCH_SIZE]
                    for tp in batch:
                        tp.capability_id = default_cap.id
                    db.flush()
                    print(f"  项目 {project.id}: 已关联 {min(i + BATCH_SIZE, len(orphan_points))}/{len(orphan_points)}")

        if not dry_run:
            db.commit()
            print("\n回填完成，已提交事务")
        else:
            db.rollback()
            print("\n[DRY-RUN] 预览完成，未写入数据库")

        # 4. 验证：检查是否还有孤立测试点
        orphan_count = db.query(TestPoint).filter(TestPoint.capability_id.is_(None)).count()
        if orphan_count > 0:
            print(f"\n警告：仍有 {orphan_count} 个测试点未关联 capability")
        else:
            print("\n验证通过：所有测试点均已关联 capability")

    except Exception as e:
        db.rollback()
        print(f"\n回填失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填测试点的 capability_id")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入数据库")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run)
