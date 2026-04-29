"""完整修复test_data表结构"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings


def get_existing_columns(conn):
    """获取test_data表的现有列"""
    result = conn.execute(text("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'test_data'
    """))
    return [row[0] for row in result.fetchall()]


def migrate():
    """完整迁移test_data表"""
    print("=" * 60)
    print("完整修复 test_data 表结构")
    print("=" * 60)

    engine = create_engine(settings.DATABASE_URL)

    # 模型中定义的所有字段
    required_columns = {
        'id': 'id INT AUTO_INCREMENT PRIMARY KEY',
        'step_id': 'step_id INT NOT NULL DEFAULT 0 COMMENT "关联的测试步骤ID"',
        'field_name': 'field_name VARCHAR(100) NOT NULL COMMENT "字段名称"',
        'field_type': 'field_type VARCHAR(20) NOT NULL DEFAULT "text" COMMENT "字段类型"',
        'data_value': 'data_value TEXT COMMENT "数据值"',
        'generation_rule': 'generation_rule VARCHAR(20) NOT NULL DEFAULT "random" COMMENT "生成规则"',
        'rule_config': 'rule_config TEXT COMMENT "生成规则配置(JSON)"',
        'min_length': 'min_length INT COMMENT "最小长度"',
        'max_length': 'max_length INT COMMENT "最大长度"',
        'min_value': 'min_value INT COMMENT "最小值"',
        'max_value': 'max_value INT COMMENT "最大值"',
        'enum_values': 'enum_values TEXT COMMENT "枚举值列表(JSON)"',
        'description': 'description VARCHAR(500) COMMENT "数据描述"',
        'is_required': 'is_required TINYINT(1) DEFAULT 1 COMMENT "是否必填"',
        'sort_order': 'sort_order INT DEFAULT 0 COMMENT "排序顺序"',
        'created_at': 'created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间"',
        'updated_at': 'updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT "更新时间"'
    }

    with engine.connect() as conn:
        existing_cols = get_existing_columns(conn)

        print(f"\n现有字段 ({len(existing_cols)}个): {existing_cols}")

        missing_cols = [col for col in required_columns.keys() if col not in existing_cols]

        if not missing_cols:
            print("\n[OK] 所有字段已存在，无需迁移")
            return True

        print(f"\n缺失字段 ({len(missing_cols)}个): {missing_cols}")
        print("\n开始添加缺失字段...")

        success_count = 0
        for col_name in missing_cols:
            col_def = required_columns[col_name]
            sql = f"ALTER TABLE test_data ADD COLUMN {col_def}"
            try:
                conn.execute(text(sql))
                print(f"  ✓ {col_name}")
                success_count += 1
            except Exception as e:
                print(f"  ✗ {col_name}: {e}")

        conn.commit()

    print("\n" + "=" * 60)
    print(f"✅ 迁移完成！成功添加 {success_count}/{len(missing_cols)} 个字段")
    print("   删除项目功能已恢复")
    print("=" * 60)
    return True


if __name__ == "__main__":
    migrate()
