"""Fix test_case.py by analyzing the AST structure and fixing indentation."""
import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Remove U+FFFD
content = content.replace('\ufffd', '')

# Fix ? at end of Chinese strings  
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)
content = re.sub(r"([\u4e00-\u9fff])\?'", r"\1'", content)

# Fix Opt[ -> Optional[
content = content.replace('Opt[', 'Optional[')
content = content.replace('from typing import List, Optional as Opt', 'from typing import List')

# Make sure Optional is imported
if 'Optional' not in content[:500]:
    content = content.replace('from typing import List', 'from typing import List, Optional', 1)

# Fix all """code patterns where docstring closing is merged with code
# But be more careful - only fix when the line has """ followed by code-like content
lines = content.split('\n')
fixed_lines = []
for i, line in enumerate(lines):
    # Pattern: """from ... or """test_case = ... etc
    # These are docstring closings merged with code
    match = re.match(r'^(\s*)"""(.+)$', line)
    if match and len(match.group(2)) > 0:
        after = match.group(2)
        indent = match.group(1)
        # Check if after looks like code
        code_keywords = ['from ', 'import ', 'def ', 'class ', 'if ', 'for ', 'while ', 
                        'return ', 'raise ', 'try:', 'except ', 'else:', 'elif ',
                        'db.', 'logger.', 'test_case', 'request.', 'current_user.',
                        'case_ids', 'success_count', 'fail_count', 'not_found',
                        'result', 'step', 'version', 'allowed', 'status',
                        'correction', 'workflow', 'message', 'detail', 'snapshot',
                        'restorable', 'enum_values', 'query', 'offset', 'total']
        is_code = any(after.strip().startswith(kw) for kw in code_keywords)
        if is_code:
            fixed_lines.append(f'{indent}"""')
            fixed_lines.append(f'{indent}{after}')
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

content = '\n'.join(fixed_lines)

# Fix lines where comment and code were merged
# Pattern: # comment    code -> # comment\n    code
lines = content.split('\n')
fixed_lines = []
for line in lines:
    # Find lines with # comment followed by 3+ spaces and then code
    match = re.match(r'^(\s+)(#\s+[^#\n]+?)\s{3,}(\w[\w.]*)', line)
    if match:
        indent, comment, code_start = match.groups()
        code_keywords = ['db', 'query', 'offset', 'for', 'if', 'return', 'raise', 
                        'existing', 'new_locator', 'service', 'steps_data', 'step_data',
                        'result', 'case_ids', 'success_count', 'fail_count', 'not_found_ids',
                        'logger', 'test_case', 'request', 'current_user', 'allowed',
                        'correction', 'workflow', 'version', 'detail', 'msg', 'message']
        if any(code_start.startswith(kw) for kw in code_keywords):
            fixed_lines.append(f'{indent}{comment}')
            fixed_lines.append(f'{indent}{code_start}{line[match.end():]}')
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

content = '\n'.join(fixed_lines)

# Fix broken string literals spanning lines
lines = content.split('\n')
fixed_lines = []
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
            fixed_lines.append(merged)
            i += 2
            continue
    
    fixed_lines.append(line)
    i += 1

content = '\n'.join(fixed_lines)

# Fix functions that lost their body indentation
# Strategy: find all 'async def' and 'def' lines, then fix indentation of subsequent lines
lines = content.split('\n')
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Check if this is a function definition
    if stripped.startswith('async def ') or stripped.startswith('def '):
        func_indent = len(line) - len(line.lstrip())
        body_indent = func_indent + 4
        
        # Fix all subsequent lines until next function/class at same or lower indent
        j = i + 1
        while j < len(lines):
            next_line = lines[j]
            next_stripped = next_line.strip()
            
            # Skip empty lines
            if not next_stripped:
                j += 1
                continue
            
            # Check if we've reached the end of this function
            # (another function/class at same or lower indent, or decorator)
            if (next_stripped.startswith('async def ') or 
                next_stripped.startswith('def ') or 
                next_stripped.startswith('class ') or
                next_stripped.startswith('@router.') or
                next_stripped.startswith('@router ')):
                if len(next_line) - len(next_line.lstrip()) <= func_indent:
                    break
            
            # Fix indentation of this line
            current_indent = len(next_line) - len(next_line.lstrip())
            
            # If line has zero indentation but should have body indentation
            if current_indent == 0 and not next_stripped.startswith('#'):
                # Determine correct indentation based on context
                # Simple heuristic: if previous non-empty line ends with :, indent more
                prev_nonempty = ''
                for k in range(j - 1, max(0, j - 5), -1):
                    if lines[k].strip():
                        prev_nonempty = lines[k]
                        break
                
                prev_indent = len(prev_nonempty) - len(prev_nonempty.lstrip()) if prev_nonempty else 0
                if prev_nonempty.rstrip().endswith(':'):
                    lines[j] = ' ' * (prev_indent + 4) + next_stripped
                else:
                    lines[j] = ' ' * max(body_indent, prev_indent) + next_stripped
            
            j += 1
    
    i += 1

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
