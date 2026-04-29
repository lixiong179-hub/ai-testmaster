import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix all broken multi-line string patterns
# Pattern: detail="Chinese text\nmore text"  -> detail="Chinese textmore text"
# These are strings that were broken across lines by PowerShell

# Fix patterns where a string literal is split across two lines
content = re.sub(
    r'detail="([^"]*)\n([^"]*)"',
    lambda m: f'detail="{m.group(1)}{m.group(2)}"',
    content
)

# Fix patterns where a string is split with a newline and no closing quote on first line
content = re.sub(
    r'detail="([^"]*)\n(\s+)([^"]*)"',
    lambda m: f'detail="{m.group(1)}{m.group(3)}"',
    content
)

# Fix remaining broken patterns - detail strings without closing paren
content = re.sub(
    r'detail="([^"]+)"\s*\n\s*\)',
    lambda m: f'detail="{m.group(1)}")',
    content
)

# Fix remaining broken patterns - msg strings split across lines
content = re.sub(
    r'msg="([^"]*)\n([^"]*)"',
    lambda m: f'msg="{m.group(1)}{m.group(2)}"',
    content
)

# Fix remaining broken patterns - f-string detail split across lines
content = re.sub(
    r'detail=f"([^"]*)\n([^"]*)"',
    lambda m: f'detail=f"{m.group(1)}{m.group(2)}"',
    content
)

# Fix remaining broken patterns - logger strings split across lines
content = re.sub(
    r'logger\.\w+\(f"([^"]*)\n([^"]*)"',
    lambda m: f'logger.warning(f"{m.group(1)}{m.group(2)}"',
    content
)

# Fix remaining broken patterns - raise ValueError split across lines
content = re.sub(
    r"raise ValueError\(f'([^']*)\n([^']*)'\)",
    lambda m: f"raise ValueError(f'{m.group(1)}{m.group(2)}')",
    content
)

content = re.sub(
    r"raise ValueError\('([^']*)\n([^']*)'\)",
    lambda m: f"raise ValueError('{m.group(1)}{m.group(2)}')",
    content
)

# Fix any remaining unterminated string on a line
lines = content.split('\n')
fixed = []
for i, line in enumerate(lines):
    # Check for unclosed double quotes
    in_string = False
    in_escape = False
    quote_count = 0
    for ch in line:
        if ch == '\\' and not in_escape:
            in_escape = True
            continue
        if ch == '"' and not in_escape:
            quote_count += 1
        in_escape = False
    
    if quote_count % 2 == 1:
        # Odd number of quotes - add closing quote
        if 'detail=' in line or 'msg=' in line or 'message' in line:
            line = line.rstrip() + '"'
    
    fixed.append(line)

content = '\n'.join(fixed)

p.write_text(content, encoding='utf-8')

import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    err_str = str(e)
    m = re.search(r'line (\d+)', err_str)
    if m:
        lineno = int(m.group(1))
        problem_lines = content.split('\n')
        for i in range(max(0, lineno-3), min(len(problem_lines), lineno+2)):
            print(f"  {i+1}: {problem_lines[i][:120]}")
    print(f"Error: {e}")
