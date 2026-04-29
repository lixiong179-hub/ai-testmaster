import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix ALL remaining broken patterns by scanning line by line
# and joining lines where a string literal is split across lines
lines = content.split('\n')
result = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if this line has an unclosed string (odd number of non-escaped double quotes)
    stripped = line.rstrip()
    
    # Count quotes (simple heuristic)
    quote_count = 0
    j = 0
    while j < len(stripped):
        if stripped[j] == '\\':
            j += 2
            continue
        if stripped[j] == '"':
            quote_count += 1
        j += 1
    
    if quote_count % 2 == 1 and i + 1 < len(lines):
        # This line has unclosed string - merge with next line(s)
        merged = stripped
        while quote_count % 2 == 1 and i + 1 < len(lines):
            i += 1
            next_line = lines[i].strip()
            merged += next_line
            # Recount quotes
            quote_count = 0
            for ch in next_line:
                if ch == '"':
                    quote_count += 1
        
        # Now fix the merged line
        # Common patterns:
        # detail="测试用例\n不存在" -> detail="测试用例不存在")
        # Make sure closing paren exists
        if 'detail=' in merged and not merged.rstrip().endswith(')'):
            merged = merged.rstrip() + ')'
        if 'msg=' in merged and not merged.rstrip().endswith(')'):
            merged = merged.rstrip() + ')'
            
        result.append(merged)
    else:
        result.append(line)
    
    i += 1

content = '\n'.join(result)

# Additional specific fixes
content = content.replace(
    'detail="测试用例\n不存在")',
    'detail="测试用例不存在")'
)
content = content.replace(
    'detail="版本记录\n不存在")',
    'detail="版本记录不存在")'
)

p.write_text(content, encoding='utf-8')

import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    err_str = str(e)
    import re
    m = re.search(r'line (\d+)', err_str)
    if m:
        lineno = int(m.group(1))
        problem_lines = content.split('\n')
        for idx in range(max(0, lineno-3), min(len(problem_lines), lineno+2)):
            print(f"  {idx+1}: {problem_lines[idx][:150]}")
    print(f"\nError: {e}")
