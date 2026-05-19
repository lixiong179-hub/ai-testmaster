import json
import logging

from app.db.database import Base
from app.db.smart_sync import smart_sync_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("=" * 70)
print("智能数据库结构同步工具")
print("=" * 70)

report = smart_sync_database(Base, auto_fix=True)

print("\n同步报告:")
print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

print("\n" + "=" * 70)
print(report['summary'])
print("=" * 70)
