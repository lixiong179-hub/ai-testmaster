import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix lines where comment and code were merged by PowerShell
# Pattern: # Chinese comment    code_on_same_line
lines = content.split('\n')
fixed = []
for line in lines:
    # Pattern: # comment followed by spaces and then code
    match = re.match(r'^(\s+)(#\s*[^\n]+?)\s{4,}(\w+.*)$', line)
    if match:
        indent, comment, code = match.groups()
        fixed.append(f'{indent}{comment}')
        fixed.append(f'{indent}{code}')
    else:
        fixed.append(line)

content = '\n'.join(fixed)

# Fix remaining ? chars that are broken Chinese
content = content.replace('?""', '"""')
content = content.replace('?"', '"')

# Remove any remaining U+FFFD
content = content.replace('\ufffd', '')

p.write_text(content, encoding='utf-8')

import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Error line: {e}")
    # Print the problematic line
    err_str = str(e)
    import re as re2
    m = re2.search(r'line (\d+)', err_str)
    if m:
        lineno = int(m.group(1))
        problem_lines = content.split('\n')[max(0,lineno-3):lineno+2]
        for i, pl in enumerate(problem_lines):
            print(f"  {lineno-3+i}: {pl[:120]}")
