import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix remaining ? characters that are broken Chinese
content = content.replace('技术视图?""', '技术视图"""')
content = content.replace('软删除?""', '软删除"""')
content = content.replace('纠正用例?""', '纠正用例"""')
content = content.replace('纠正状态?""', '纠正状态"""')
content = content.replace('工作流状态?""', '工作流状态"""')
content = content.replace('请求模型?""', '请求模型"""')
content = content.replace('指定版本?""', '指定版本"""')

# Fix any remaining ? inside strings that should be Chinese
lines = content.split('\n')
fixed = []
for line in lines:
    # Fix docstrings with trailing ?
    if '"""' in line and line.strip().endswith('?""'):
        line = line.replace('?""', '"""')
    # Fix detail strings with trailing ?
    if 'detail=' in line and line.strip().endswith('?"'):
        line = line.replace('?"', '"')
    # Fix message strings with trailing ?
    if '"message"' in line and line.strip().endswith('?"'):
        line = line.replace('?"', '"')
    fixed.append(line)

content = '\n'.join(fixed)

# Remove any remaining U+FFFD
content = content.replace('\ufffd', '')

p.write_text(content, encoding='utf-8')

import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
