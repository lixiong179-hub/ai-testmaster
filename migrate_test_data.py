"""数据库迁移脚本 - 修复test_data表缺少step_id字段的问题"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings


def migrate():
    """执行数据库迁移"""
    print("=" * 60)
    print("开始数据库迁移：修复 test_data.step_id 字段缺失")
    print("=" * 60)

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 检查字段是否存在
        print("\n[1/3] 检查 step_id 字段...")
        sql_check = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'test_data' AND COLUMN_NAME = 'step_id'"
        result = conn.execute(text(sql_check))

        if result.fetchone():
            print("[OK] step_id 已存在，无需迁移")
            return True

        print("[INFO] step_id 不存在，开始添加...")

        # 添加字段
        print("\n[2/3] 添加 step_id 字段...")
        sql_add = "ALTER TABLE test_data ADD COLUMN step_id INT NOT NULL DEFAULT 0 COMMENT '关联的测试步骤ID'"
        try:
            conn.execute(text(sql_add))
            print("[OK] 成功添加 step_id")
        except Exception as e:
            print(f"[ERROR] 失败: {e}")
            return False

        # 尝试添加外键
        print("\n[3/3] 添加外键约束...")
        try:
            sql_fk = "ALTER TABLE test_data ADD CONSTRAINT fk_test_data_step_id FOREIGN KEY (step_id) REFERENCES test_steps(id) ON DELETE CASCADE"
            conn.execute(text(sql_fk))
            print("[OK] 外键约束已添加")
        except Exception as e:
            print(f"[WARN] 外键添加失败（非致命）: {e}")

        conn.commit()

    print("\n" + "=" * 60)
    print("✅ 迁移完成！删除项目功能已恢复")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
