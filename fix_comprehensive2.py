"""Comprehensive auto-fix for test_case.py - fix all indentation and merged line issues."""
import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Remove U+FFFD
content = content.replace('\ufffd', '')

# Fix all remaining ? at end of Chinese strings
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)
content = re.sub(r'([\u4e00-\u9fff])\?\'', r"\1'", content)

# Fix """code -> """\ncode (docstring closing merged with code)
# But only when """ is followed by code, not docstring text
content = re.sub(r'"""(\s+)(from |import |def |class |if |for |while |return |raise |try:|except |else:|elif |async |db\.|logger|test_case|request|current_user|case_|success_|fail_|not_|result|step|version|allowed|status|correction|workflow|message|detail|snapshot|restorable|enum_values)', r'"""\n\1\2', content)

# Fix )code -> )\ncode
content = re.sub(r'\)(\n?\s+)(from |import |def |class |if |for |while |return |raise |try:|except |else:|elif |async def |case_ids|success_count|fail_count|not_found|db\.|logger|test_case|request|current_user|enum_values)', r')\n\2', content)

# Fix broken string literals spanning lines
# Read line by line and fix
lines = content.split('\n')
result = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    
    # Count double quotes (simple)
    temp = stripped.replace('\\"', '  ')
    quote_count = temp.count('"')
    
    if quote_count % 2 == 1 and i + 1 < len(lines):
        # Odd quotes - might be broken string
        if any(kw in stripped for kw in ['detail=', 'msg=', 'message=', 'logger.']):
            next_line = lines[i + 1].strip()
            merged = stripped + next_line
            if not merged.rstrip().endswith(')') and ('raise' in stripped or 'return' in stripped or 'logger' in stripped):
                merged = merged.rstrip() + ')'
            result.append(merged)
            i += 2
            continue
    
    result.append(line)
    i += 1

content = '\n'.join(result)

# Fix functions that lost their body indentation
# Pattern: function def followed by unindented code
# Find all async def / def lines and ensure next line is indented
lines = content.split('\n')
result = []
for i, line in enumerate(lines):
    result.append(line)
    if i + 1 < len(lines):
        next_line = lines[i + 1]
        # If current line ends with : and next line has no indentation
        if line.rstrip().endswith(':') and next_line.strip() and not next_line[0].isspace():
            # Check if it's a function/class definition
            if any(line.strip().startswith(kw) for kw in ['async def', 'def ', 'class ', 'if ', 'for ', 'while ', 'try:', 'except', 'else:', 'elif ', 'with ']):
                # Add proper indentation to next line
                indent = '    '  # Default 4 spaces
                if line.startswith('    '):
                    indent = '    ' * 2
                result[-1] = line  # Keep current
                # We'll fix the next line when we get to it
                lines[i + 1] = indent + next_line.strip()

content = '\n'.join(result)

# Fix specific remaining broken patterns
# Fix: from datetime import datetime as dt  (should be at module level or inside function with indent)
# Fix: case_ids = request.caseIds  (should be inside function with indent)

# Fix the restore function and other functions that lost indentation
# Find function boundaries and fix indentation within them
functions = []
in_function = False
func_start = -1
func_indent = 0

lines = content.split('\n')
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('async def ') or stripped.startswith('def '):
        if in_function:
            functions.append((func_start, i - 1, func_indent))
        in_function = True
        func_start = i
        func_indent = len(line) - len(line.lstrip())
    elif stripped.startswith('@') and i + 1 < len(lines) and (lines[i+1].strip().startswith('async def ') or lines[i+1].strip().startswith('def ')):
        if in_function:
            functions.append((func_start, i - 1, func_indent))
        in_function = False
        func_start = i
        func_indent = len(line) - len(line.lstrip())

if in_function:
    functions.append((func_start, len(lines) - 1, func_indent))

# Fix indentation within each function
for start, end, base_indent in functions:
    body_indent = base_indent + 4
    for i in range(start + 1, end + 1):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            continue
        current_indent = len(line) - len(line.lstrip())
        # If line has no indentation but should have some
        if current_indent == 0 and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
            # This line lost its indentation
            lines[i] = ' ' * body_indent + stripped

content = '\n'.join(lines)

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
        for idx in range(max(0, lineno-3), min(len(problem_lines), lineno+2)):
            print(f"  {idx+1}: {problem_lines[idx][:150]}")
    print(f"\nError: {e}")
