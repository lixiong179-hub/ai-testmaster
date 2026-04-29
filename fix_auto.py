"""Auto-fix test_case.py by reading it line by line and fixing common patterns."""
import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Strategy: fix all known patterns systematically

# 1. Fix """code -> """\ncode (docstring closing merged with code)
content = re.sub(r'"""(\w)', r'"""\n\1', content)
# But don't break opening docstrings like """text
# Only fix when """ is at end of a line followed by code
lines = content.split('\n')
fixed = []
for line in lines:
    # Fix: """code_pattern where code starts right after """
    # But preserve: """docstring text""" and """\n    text\n    """
    match = re.match(r'^(\s+)"""(.+)$', line)
    if match and not line.strip().startswith('"""') and len(line.strip()) > 3:
        # This is a closing """ followed by code on same line
        indent = match.group(1)
        rest = match.group(2)
        # Check if rest looks like code (starts with keyword or identifier)
        if re.match(r'^(from |import |def |class |if |for |while |return |raise |try|except|else|elif|async |case_|success_|fail_|not_|db\.|logger|test_case|request|current_user|result|step|version|allowed|status|correction|workflow|message|detail)', rest):
            fixed.append(f'{indent}"""')
            fixed.append(f'{indent}{rest}')
        else:
            fixed.append(line)
    else:
        fixed.append(line)
content = '\n'.join(fixed)

# 2. Fix )code -> )\ncode patterns (closing paren merged with code)
content = re.sub(r'\)(from |import |def |class |if |for |while |return |raise |try:|except |else:|elif |async def |case_ids|success_count|fail_count|not_found|db\.|logger|test_case|request|current_user)', r')\n\1', content)

# 3. Fix broken string literals that span lines
# Pattern: detail="text\nmore" -> detail="textmore"
lines = content.split('\n')
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    
    # Count non-escaped double quotes
    temp = stripped.replace('\\"', '  ')
    quote_count = temp.count('"')
    
    if quote_count % 2 == 1 and i + 1 < len(lines):
        # Odd quotes - might be broken string
        if any(kw in stripped for kw in ['detail=', 'msg=', 'message']):
            next_stripped = lines[i + 1].strip()
            # Merge lines
            merged = stripped + next_stripped
            if not merged.rstrip().endswith(')'):
                merged = merged.rstrip() + ')'
            fixed.append(merged)
            i += 2
            continue
    
    fixed.append(line)
    i += 1

content = '\n'.join(fixed)

# 4. Fix comment+code merged lines
# Only fix when there's a # comment followed by 4+ spaces and then code
lines = content.split('\n')
fixed = []
for line in lines:
    match = re.match(r'^(\s+)(#\s+[^\n]+?)\s{4,}([a-zA-Z_]\w*)', line)
    if match:
        indent, comment, code_start = match.groups()
        # Check if code_start looks like a variable/keyword
        if code_start in ['db', 'query', 'offset', 'for', 'if', 'return', 'raise', 'existing', 'new_locator', 'service', 'steps_data', 'step_data', 'result', 'case_ids', 'success_count', 'fail_count', 'not_found_ids', 'logger', 'test_case', 'request', 'current_user', 'allowed', 'correction', 'workflow', 'version', 'detail', 'msg', 'message']:
            fixed.append(f'{indent}{comment}')
            fixed.append(f'{indent}{code_start}{line[match.end():]}')
        else:
            fixed.append(line)
    else:
        fixed.append(line)
content = '\n'.join(fixed)

# 5. Remove remaining U+FFFD
content = content.replace('\ufffd', '')

# 6. Fix remaining ? at end of strings
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)

p.write_text(content, encoding='utf-8')

import py_compile
max_attempts = 50
attempt = 0
while attempt < max_attempts:
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"Syntax OK after {attempt} fix iterations!")
        break
    except py_compile.PyCompileError as e:
        attempt += 1
        err_str = str(e)
        m = re.search(r'line (\d+)', err_str)
        if not m:
            print(f"Cannot parse error: {e}")
            break
        lineno = int(m.group(1))
        problem_lines = content.split('\n')
        
        if lineno <= 0 or lineno > len(problem_lines):
            break
            
        problem_line = problem_lines[lineno - 1]
        
        # Auto-fix common patterns
        if '"""' in problem_line and not problem_line.strip().startswith('"""'):
            # Docstring closing merged with code
            idx = problem_line.index('"""')
            before = problem_line[:idx + 3]
            after = problem_line[idx + 3:]
            if after.strip():
                indent = len(problem_line) - len(problem_line.lstrip())
                problem_lines[lineno - 1] = before
                problem_lines.insert(lineno, ' ' * indent + after.strip())
                content = '\n'.join(problem_lines)
                p.write_text(content, encoding='utf-8')
                continue
        
        if 'IndentationError' in err_str:
            # Fix indentation
            prev_line = problem_lines[lineno - 2] if lineno >= 2 else ''
            prev_indent = len(prev_line) - len(prev_line.lstrip())
            problem_lines[lineno - 1] = ' ' * prev_indent + problem_line.lstrip()
            content = '\n'.join(problem_lines)
            p.write_text(content, encoding='utf-8')
            continue
            
        # Can't auto-fix - report and break
        for idx in range(max(0, lineno-3), min(len(problem_lines), lineno+2)):
            print(f"  {idx+1}: {problem_lines[idx][:150]}")
        print(f"\nCannot auto-fix error at line {lineno}: {e}")
        break
