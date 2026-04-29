"""测试智能数据库同步功能"""
import sys
import logging

sys.path.insert(0, '.')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("=" * 70)
print("测试智能数据库同步工具")
print("=" * 70)

# 导入所有模型（确保注册到Base.metadata）
from app.db.database import Base
from app.models import user
from app.models import project
from app.models import test_data
from app.models import test_case
from app.models import test_task
from app.models import test_point

print(f"\n已注册的表 ({len(Base.metadata.tables)}个):")
for table_name in sorted(Base.metadata.tables.keys()):
    print(f"  - {table_name}")

# 执行智能同步
from app.db.smart_sync import smart_sync_database

print("\n开始智能同步...")
report = smart_sync_database(Base, auto_fix=True)

print("\n" + "=" * 70)
print("同步报告")
print("=" * 70)
print(f"总表数: {report['total_tables']}")
print(f"已同步: {report['synced']}")
print(f"已修复: {report['fixed']}")
print(f"错误数: {report['errors']}")
print(f"\n摘要: {report['summary']}")

if report['details']:
    print("\n详细结果:")
    for detail in report['details']:
        if detail['status'] != 'synced':
            print(f"  表 {detail['table']}:")
            print(f"    状态: {detail['status']}")
            if detail.get('missing_columns'):
                print(f"    缺失字段: {detail['missing_columns']}")
            if detail.get('fixed_columns'):
                print(f"    已修复字段: {detail['fixed_columns']}")
            if detail.get('errors'):
                print(f"    错误: {detail['errors']}")

print("=" * 70)
