"""临时脚本: 修复 test_decision_application_service.py 中的编码损坏"""
import re

path = r"d:\PythonFile\ai-testmaster\tests\services\test_decision_application_service.py"

with open(path, "rb") as f:
    content = f.read()

text = content.decode("utf-8", errors="replace")

# 修复 "功能已下线" 的损坏
text = text.replace('功能已下\ufffd,', '功能已下线",')

# 修复 "待废弃用例" 的损坏
text = text.replace('待废弃用\ufffd,', '待废弃用例",')

# 检查还有没有残留的损坏字符
for i, line in enumerate(text.split("\n"), 1):
    if "\ufffd" in line:
        print(f"Line {i}: {line.strip()}")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Done fixing encoding issues.")
