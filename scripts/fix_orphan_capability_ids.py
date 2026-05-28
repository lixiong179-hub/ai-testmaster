"""
数据修复脚本：扫描 test_points 中 capability_id 为 NULL 的孤儿记录

硬删除时代遗留的 capability_id IS NULL 记录，大部分因关联的 capability 已被物理删除
而无法修复。本脚本主要做统计报告，对可修复的记录尝试匹配修复。

使用方式：
    python -m scripts.fix_orphan_capability_ids
"""
import sys
from sqlalchemy import text
from scripts.cli_utils import build_session


def scan_orphan_test_points(session) -> dict:
    """扫描 test_points 中 capability_id 为 NULL 的记录并生成统计报告。

    Args:
        session: 数据库会话。

    Returns:
        统计报告字典，包含总数、可修复数、不可修复数等。
    """
    orphan_count = session.execute(text(
        "SELECT COUNT(*) FROM test_points WHERE capability_id IS NULL"
    )).scalar()

    if orphan_count == 0:
        print("[INFO] 未发现 capability_id 为 NULL 的孤儿记录，数据完好。")
        return {"total_orphans": 0, "repairable": 0, "unrepairable": 0}

    print(f"[INFO] 发现 {orphan_count} 条 capability_id 为 NULL 的记录。")

    # 尝试通过 project_id + module 推断可能的 capability
    # 由于硬删除后 capability 记录已不存在，大部分 NULL 实际无法修复
    potential_repairs = session.execute(text(
        """
        SELECT tp.id AS test_point_id, tp.project_id, tp.module,
               tc.id AS matched_capability_id, tc.key AS matched_key
        FROM test_points tp
        LEFT JOIN test_capabilities tc
            ON tc.project_id = tp.project_id
            AND tc.key = tp.module
            AND tc.status != 'archived'
        WHERE tp.capability_id IS NULL
        """
    )).fetchall()

    repairable = [row for row in potential_repairs if row.matched_capability_id is not None]
    unrepairable_count = orphan_count - len(repairable)

    print(f"[INFO] 可通过 module 匹配修复: {len(repairable)} 条")
    print(f"[INFO] 无法修复（capability 已不存在）: {unrepairable_count} 条")

    if repairable:
        print("\n[DETAIL] 可修复记录：")
        for row in repairable:
            print(
                f"  test_point.id={row.test_point_id}, "
                f"project_id={row.project_id}, module='{row.module}' "
                f"-> capability.id={row.matched_capability_id}, key='{row.matched_key}'"
            )

    return {
        "total_orphans": orphan_count,
        "repairable": len(repairable),
        "unrepairable": unrepairable_count,
        "repair_details": [
            {
                "test_point_id": row.test_point_id,
                "project_id": row.project_id,
                "module": row.module,
                "matched_capability_id": row.matched_capability_id,
                "matched_key": row.matched_key,
            }
            for row in repairable
        ],
    }


def apply_repairs(session, report: dict) -> int:
    """根据扫描报告执行修复。

    Args:
        session: 数据库会话。
        report: scan_orphan_test_points 返回的报告。

    Returns:
        成功修复的记录数。
    """
    repair_details = report.get("repair_details", [])
    if not repair_details:
        print("[INFO] 无可修复记录，跳过。")
        return 0

    fixed = 0
    for item in repair_details:
        try:
            session.execute(
                text(
                    "UPDATE test_points SET capability_id = :cap_id "
                    "WHERE id = :tp_id AND capability_id IS NULL"
                ),
                {"cap_id": item["matched_capability_id"], "tp_id": item["test_point_id"]},
            )
            fixed += 1
        except Exception as e:
            print(f"[WARN] 修复 test_point.id={item['test_point_id']} 失败: {e}")

    session.commit()
    print(f"[INFO] 成功修复 {fixed} 条记录。")
    return fixed


def main() -> None:
    """脚本入口：扫描并可选修复孤儿 capability_id。"""
    session, engine = build_session()
    try:
        report = scan_orphan_test_points(session)

        if report["repairable"] > 0:
            answer = input("\n是否执行修复？(y/N): ").strip().lower()
            if answer == "y":
                apply_repairs(session, report)
            else:
                print("[INFO] 跳过修复。")

        print("\n[DONE] 扫描完成。")
    except Exception as e:
        print(f"[ERROR] 脚本执行失败: {e}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
