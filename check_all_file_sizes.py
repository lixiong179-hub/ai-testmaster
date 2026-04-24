
"""检查所有Service文件的行数"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
APP_DIR = ROOT / "app" / "services"

files_over_300 = []
all_files = []

for py_file in APP_DIR.rglob("*.py"):
    if '__pycache__' in str(py_file):
        continue
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            line_count = len(lines)
            all_files.append((py_file.relative_to(ROOT), line_count))
            if line_count > 300:
                files_over_300.append((py_file.relative_to(ROOT), line_count))
    except Exception as e:
        print(f"Error reading {py_file}: {e}")

print("="*60)
print("所有Service文件行数统计")
print("="*60)

# 按行数排序
all_files.sort(key=lambda x: x[1], reverse=True)

print(f"\n总计 {len(all_files)} 个Python文件")
print(f"超过300行的文件: {len(files_over_300)} 个")

if files_over_300:
    print("\n超过300行的文件:")
    for path, lines in files_over_300:
        print(f"  - {path}: {lines}行")

print("\n前20个最大的文件:")
for path, lines in all_files[:20]:
    marker = " ✗" if lines > 300 else ""
    print(f"  {path}: {lines}行{marker}")
