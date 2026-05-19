# -*- coding: utf-8 -*-
"""
全面数据库字段检查工具
对比ORM模型定义与实际数据库表结构，找出所有缺失的字段
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text
from app.core.config import settings
from app.db.database import Base
from app.models import *

def check_database_completeness():
    """
    全面检查数据库完整性：
    1. 检查所有模型定义的表是否都存在
    2. 检查每个表的字段是否完整
    3. 生成修复SQL
    """
    
    print("=" * 80)
    print("AI测试平台 - 数据库完整性全面检查")
    print("=" * 80)
    
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    db_tables = set(inspector.get_table_names())
    
    model_tables = set(Base.metadata.tables.keys())
    
    print(f"\n【统计信息】")
    print(f"模型定义的表数量: {len(model_tables)}")
    print(f"数据库中的表数量: {len(db_tables)}")
    
    missing_tables = model_tables - db_tables
    extra_tables = db_tables - model_tables
    
    if missing_tables:
        print(f"\n❌ 缺失的表（{len(missing_tables)}个）:")
        for table in sorted(missing_tables):
            print(f"  - {table}")
    else:
        print(f"\n✅ 所有模型定义的表都已存在")
    
    if extra_tables:
        print(f"\n⚠️  数据库中多余的表（{len(extra_tables)}个）:")
        for table in sorted(extra_tables):
            print(f"  + {table}")
    
    print("\n" + "=" * 80)
    print("【逐表字段检查】")
    print("=" * 80)
    
    all_missing_columns = []
    all_fix_sqls = []
    
    for table_name in sorted(model_tables):
        if table_name in ['user_role', 'role_permission']:
            continue
            
        print(f"\n📋 表: {table_name}")
        
        if table_name not in Base.metadata.tables:
            print(f"   ⚠️  模型中未找到此表定义")
            continue
            
        model_table = Base.metadata.tables[table_name]
        model_columns = {col.name: col for col in model_table.columns}
        
        try:
            db_columns_list = inspector.get_columns(table_name)
            db_columns = {col['name']: col for col in db_columns_list}
        except Exception as e:
            print(f"   ❌ 无法获取表信息: {e}")
            continue
        
        missing_cols = set(model_columns.keys()) - set(db_columns.keys())
        extra_cols = set(db_columns.keys()) - set(model_columns.keys())
        
        if missing_cols:
            print(f"   ❌ 缺失字段 ({len(missing_cols)}个):")
            for col_name in sorted(missing_cols):
                col = model_columns[col_name]
                print(f"      - {col_name} ({col.type})")
                
                nullable = "NULL" if col.nullable else "NOT NULL"
                default = ""
                if col.default and str(col.default) != 'None':
                    default_arg = str(col.default.arg) if hasattr(col.default, 'arg') else str(col.default)
                    default = f" DEFAULT {default_arg}"
                    
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col.type} {nullable}{default}"
                all_fix_sqls.append(sql)
                all_missing_columns.append((table_name, col_name, str(col.type)))
        else:
            print(f"   ✅ 字段完整 ({len(model_columns)}个)")
        
        if extra_cols:
            print(f"   ⚠️  多余字段 ({len(extra_cols)}个): {sorted(extra_cols)}")
    
    print("\n" + "=" * 80)
    print("【检查结果汇总】")
    print("=" * 80)
    
    total_missing = len(all_missing_columns)
    
    if total_missing == 0:
        print("\n🎉 完美！所有数据库表和字段都是完整的！")
        return {
            'status': 'perfect',
            'missing_tables': len(missing_tables),
            'missing_columns': total_missing,
            'fix_sqls': []
        }
    else:
        print(f"\n⚠️  发现问题:")
        print(f"   - 缺失的表: {len(missing_tables)} 个")
        print(f"   - 缺失的字段: {total_missing} 个")
        
        print(f"\n【修复SQL语句】")
        print("=" * 80)
        for i, sql in enumerate(all_fix_sqls, 1):
            print(f"{i}. {sql};")
        
        return {
            'status': 'needs_fix',
            'missing_tables': list(missing_tables),
            'missing_columns': all_missing_columns,
            'fix_sqls': all_fix_sqls
        }


def auto_fix_database():
    """
    自动修复数据库：添加所有缺失的字段
    """
    result = check_database_completeness()
    
    if result['status'] == 'perfect':
        print("\n无需修复，数据库已是最新状态！")
        return
    
    print("\n" + "=" * 80)
    print("【开始自动修复】")
    print("=" * 80)
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        for sql in result['fix_sqls']:
            try:
                conn.execute(text(sql))
                print(f"✅ 执行成功: {sql[:60]}...")
            except Exception as e:
                print(f"❌ 执行失败: {sql[:60]}...")
                print(f"   错误: {e}")
        
        conn.commit()
    
    print("\n" + "=" * 80)
    print("✅ 自动修复完成！请重新运行检查以验证。")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库完整性检查工具')
    parser.add_argument('--fix', action='store_true', help='自动修复缺失的字段')
    args = parser.parse_args()
    
    if args.fix:
        auto_fix_database()
    else:
        check_database_completeness()
