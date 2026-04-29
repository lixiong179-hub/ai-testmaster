import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix patterns where docstring closing """ was merged with code on same line
# Pattern: """code_on_next_line -> """\ncode_on_next_line
content = re.sub(r'"""(\w)', r'"""\n\1', content)

# Fix patterns where closing paren ) was merged with code on same line
# Pattern: )code -> )\ncode  (but not inside strings)
# Only fix when ) is followed by a keyword or identifier on the same line
content = re.sub(r'\)(\s+)(async def |def |class |if |for |while |return |raise |try:|except |else:|elif )', r')\n\1\2', content)

# Fix patterns where a string literal is split across lines (no closing quote on first line)
# Pattern: detail="Chinese text\nmore text"  -> detail="Chinese textmore text"
# This is trickier - we need to find lines with odd quote count and merge
lines = content.split('\n')
result = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    
    # Count double quotes (simple count, ignoring escaped ones)
    temp = stripped.replace('\\"', '')
    quote_count = temp.count('"')
    
    # If odd number of quotes and it looks like a string literal line
    if quote_count % 2 == 1 and ('detail=' in stripped or 'msg=' in stripped or 'message' in stripped):
        # This line has an unclosed string - merge with next line
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Merge: remove the broken end and append next line content
            merged = stripped + next_line
            # Ensure closing paren
            if not merged.rstrip().endswith(')'):
                merged = merged.rstrip() + ')'
            result.append(merged)
            i += 2  # Skip the next line since we merged it
            continue
    
    result.append(line)
    i += 1

content = '\n'.join(result)

# Fix specific known broken patterns
content = content.replace('detail="测试用例不存在"', 'detail="测试用例不存在"')
content = content.replace('detail="版本记录不存在"', 'detail="版本记录不存在"')

# Fix lines where comment and code were merged
# Pattern: # comment    code -> # comment\n    code
content = re.sub(r'(\s+)(#\s+[^\n]{5,}?)\s{3,}(\w[\w.]*)', r'\1\2\n\1\3', content)

# Remove any remaining U+FFFD
content = content.replace('\ufffd', '')

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
