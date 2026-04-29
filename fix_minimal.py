"""Minimal fix: just make test_case.py compile. Only fix actual syntax errors."""
import pathlib
import re
import py_compile

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')

# Read the file
content = p.read_text(encoding='utf-8', errors='replace')

# Remove U+FFFD replacement chars
content = content.replace('\ufffd', '')

# Fix ? at end of Chinese strings  
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)
content = re.sub(r"([\u4e00-\u9fff])\?'", r"\1'", content)

# Fix Opt[ -> Optional[
content = content.replace('Opt[', 'Optional[')

# Remove the redundant import
content = content.replace('from typing import List, Optional as Opt', 'from typing import List')

# Make sure Optional is imported
if 'from typing import' in content and 'Optional' not in content.split('from typing import')[1].split('\n')[0]:
    content = content.replace('from typing import List', 'from typing import List, Optional')

p.write_text(content, encoding='utf-8')

# Now iteratively fix syntax errors
max_iterations = 100
for iteration in range(max_iterations):
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"Syntax OK after {iteration} iterations!")
        break
    except py_compile.PyCompileError as e:
        err_str = str(e)
        m = re.search(r'line (\d+)', err_str)
        if not m:
            print(f"Cannot parse error: {e}")
            break
        
        lineno = int(m.group(1))
        lines = content.split('\n')
        
        if lineno <= 0 or lineno > len(lines):
            break
        
        problem_line = lines[lineno - 1]
        err_type = 'IndentationError' if 'IndentationError' in err_str else 'SyntaxError'
        
        if err_type == 'IndentationError' and 'unexpected indent' in err_str:
            # Line has too much indentation - reduce it
            prev_line = lines[lineno - 2] if lineno >= 2 else ''
            prev_indent = len(prev_line) - len(prev_line.lstrip()) if prev_line.strip() else 0
            # Set indent to match previous non-empty line
            lines[lineno - 1] = ' ' * prev_indent + problem_line.lstrip()
            content = '\n'.join(lines)
            p.write_text(content, encoding='utf-8')
            continue
        
        if err_type == 'IndentationError' and 'does not match' in err_str:
            # Indentation doesn't match - fix it
            # Find the enclosing block's indentation
            for j in range(lineno - 2, max(0, lineno - 20), -1):
                prev = lines[j]
                if prev.strip() and not prev.strip().startswith('#'):
                    prev_indent = len(prev) - len(prev.lstrip())
                    if prev.rstrip().endswith(':'):
                        lines[lineno - 1] = ' ' * (prev_indent + 4) + problem_line.lstrip()
                    else:
                        lines[lineno - 1] = ' ' * prev_indent + problem_line.lstrip()
                    break
            content = '\n'.join(lines)
            p.write_text(content, encoding='utf-8')
            continue
        
        if 'unterminated string literal' in err_str:
            # Add closing quote
            stripped = problem_line.rstrip()
            if stripped.count('"') % 2 == 1:
                lines[lineno - 1] = stripped + '"'
            elif stripped.count("'") % 2 == 1:
                lines[lineno - 1] = stripped + "'"
            content = '\n'.join(lines)
            p.write_text(content, encoding='utf-8')
            continue
        
        if 'unmatched' in err_str and ')' in err_str:
            # Extra closing paren - remove it
            lines[lineno - 1] = problem_line.replace(')', '', 1)
            content = '\n'.join(lines)
            p.write_text(content, encoding='utf-8')
            continue
        
        # Can't auto-fix - report
        for idx in range(max(0, lineno-3), min(len(lines), lineno+2)):
            print(f"  {idx+1}: {lines[idx][:150]}")
        print(f"\nCannot auto-fix at line {lineno} (iteration {iteration}): {e}")
        break
