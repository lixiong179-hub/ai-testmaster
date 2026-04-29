"""Fix test_case.py by re-indenting all code that lost its indentation."""
import pathlib
import re
import py_compile

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')

# Read and clean
content = p.read_text(encoding='utf-8', errors='replace')
content = content.replace('\ufffd', '')
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)
content = re.sub(r"([\u4e00-\u9fff])\?'", r"\1'", content)
content = content.replace('Opt[', 'Optional[')
content = content.replace('from typing import List, Optional as Opt', 'from typing import List')
if 'Optional' not in content[:500]:
    content = content.replace('from typing import List', 'from typing import List, Optional', 1)

# Fix docstring closings merged with code
content = re.sub(r'"""(from |import |def |class |if |for |while |return |raise |try:|except |else:|elif |async |db\.|logger|test_case|request|current_user|case_|success_|fail_|not_|result|step|version|allowed|status|correction|workflow|message|detail|snapshot|restorable|enum_values|query|offset|total)', r'"""\n\1', content)

# Fix comment+code merged lines
lines = content.split('\n')
fixed = []
for line in lines:
    match = re.match(r'^(\s+)(#\s+[^\n]+?)\s{3,}(\w[\w.]*)', line)
    if match:
        indent, comment, code_start = match.groups()
        code_keywords = ['db', 'query', 'offset', 'for', 'if', 'return', 'raise', 
                        'existing', 'new_locator', 'service', 'steps_data', 'step_data',
                        'result', 'case_ids', 'success_count', 'fail_count', 'not_found_ids',
                        'logger', 'test_case', 'request', 'current_user', 'allowed',
                        'correction', 'workflow', 'version', 'detail', 'msg', 'message']
        if any(code_start.startswith(kw) for kw in code_keywords):
            fixed.append(f'{indent}{comment}')
            fixed.append(f'{indent}{code_start}{line[match.end():]}')
        else:
            fixed.append(line)
    else:
        fixed.append(line)
content = '\n'.join(fixed)

# Fix broken string literals spanning lines
lines = content.split('\n')
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    temp = stripped.replace('\\"', '  ')
    quote_count = temp.count('"')
    if quote_count % 2 == 1 and i + 1 < len(lines):
        if any(kw in stripped for kw in ['detail=', 'msg=', 'message=']):
            next_line = lines[i + 1].strip()
            merged = stripped + next_line
            if not merged.rstrip().endswith(')'):
                merged = merged.rstrip() + ')'
            fixed.append(merged)
            i += 2
            continue
    fixed.append(line)
    i += 1
content = '\n'.join(fixed)

# Fix zero-indented code inside functions
# Strategy: track function scope and fix indentation
lines = content.split('\n')
result = []
scope_stack = [0]  # Stack of indentation levels

for i, line in enumerate(lines):
    stripped = line.strip()
    
    if not stripped:
        result.append(line)
        continue
    
    current_indent = len(line) - len(line.lstrip())
    
    # Track scope changes
    if stripped.startswith('async def ') or stripped.startswith('def ') or stripped.startswith('class '):
        # New function/class - update scope
        while scope_stack and scope_stack[-1] >= current_indent:
            scope_stack.pop()
        scope_stack.append(current_indent)
    elif stripped.startswith('@'):
        pass  # Decorator - don't change scope
    
    # Fix zero-indented code that should be inside a function
    if current_indent == 0 and scope_stack and scope_stack[-1] >= 0:
        # This line has no indentation but we're inside a scope
        # Check if it's a top-level statement or should be indented
        top_level_keywords = ['from ', 'import ', 'async def ', 'def ', 'class ', '@', '#', '"""', "'''", 'WORKFLOW_', 'STATUS_', 'CORRECTION_', 'router', 'VALID_']
        is_top_level = any(stripped.startswith(kw) for kw in top_level_keywords)
        
        if not is_top_level:
            # This should be indented - add the correct indentation
            # Find the expected indent from the scope stack
            expected_indent = scope_stack[-1] + 4
            line = ' ' * expected_indent + stripped
    
    result.append(line)

content = '\n'.join(result)

p.write_text(content, encoding='utf-8')

# Verify
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
