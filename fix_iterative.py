"""Fix test_case.py - comprehensive fix for all indentation and broken patterns."""
import pathlib
import re
import py_compile

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Clean up
content = content.replace('\ufffd', '')
content = re.sub(r'([\u4e00-\u9fff])\?"', r'\1"', content)
content = re.sub(r'([\u4e00-\u9fff])\?"""', r'\1"""', content)
content = re.sub(r"([\u4e00-\u9fff])\?'", r"\1'", content)
content = content.replace('Opt[', 'Optional[')

# Fix all over-indented class/def at module level
# Pattern: lines starting with extra spaces before class/def that should be at module level
lines = content.split('\n')
fixed = []
prev_was_comment = False
prev_indent = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        fixed.append(line)
        continue
    
    current_indent = len(line) - len(line.lstrip())
    
    # Fix: class/def that should be at module level but got indented
    if stripped.startswith('class ') and current_indent > 0:
        # Check if previous non-empty line is a comment or decorator at module level
        prev_nonempty = ''
        for j in range(i-1, max(0, i-5), -1):
            if lines[j].strip():
                prev_nonempty = lines[j]
                break
        prev_ne_indent = len(prev_nonempty) - len(prev_nonempty.lstrip()) if prev_nonempty else 0
        
        if prev_ne_indent == 0 or prev_nonempty.strip().startswith('#'):
            # This class should be at module level
            line = stripped
            current_indent = 0
    
    # Fix: over-indented code inside try/except blocks
    # Pattern: except at wrong indent level
    if stripped.startswith('except ') and current_indent > 0:
        # Find the matching try
        for j in range(i-1, max(0, i-20), -1):
            prev = lines[j].strip()
            if prev.startswith('try:'):
                try_indent = len(lines[j]) - len(lines[j].lstrip())
                if current_indent != try_indent:
                    line = ' ' * try_indent + stripped
                    current_indent = try_indent
                break
    
    fixed.append(line)

content = '\n'.join(fixed)

# Iteratively fix remaining syntax errors
for iteration in range(200):
    try:
        py_compile.compile(str(p), doraise=True)
        # Also write the fixed content
        p.write_text(content, encoding='utf-8')
        print(f"Syntax OK after {iteration} iterations!")
        break
    except py_compile.PyCompileError as e:
        err_str = str(e)
        m = re.search(r'line (\d+)', err_str)
        if not m:
            p.write_text(content, encoding='utf-8')
            print(f"Cannot parse error: {e}")
            break
        
        lineno = int(m.group(1))
        lines = content.split('\n')
        
        if lineno <= 0 or lineno > len(lines):
            p.write_text(content, encoding='utf-8')
            break
        
        problem_line = lines[lineno - 1]
        stripped = problem_line.strip()
        
        fixed_line = None
        
        if 'IndentationError' in err_str:
            if 'unexpected indent' in err_str:
                # Too much indentation - find correct indent from context
                for j in range(lineno - 2, max(0, lineno - 10), -1):
                    prev = lines[j]
                    if prev.strip() and not prev.strip().startswith('#'):
                        prev_indent = len(prev) - len(prev.lstrip())
                        if prev.rstrip().endswith(':'):
                            fixed_line = ' ' * (prev_indent + 4) + stripped
                        else:
                            fixed_line = ' ' * prev_indent + stripped
                        break
            elif 'does not match' in err_str or 'expected an indented block' in err_str:
                # Wrong indent level
                for j in range(lineno - 2, max(0, lineno - 10), -1):
                    prev = lines[j]
                    if prev.strip() and not prev.strip().startswith('#'):
                        prev_indent = len(prev) - len(prev.lstrip())
                        if prev.rstrip().endswith(':'):
                            fixed_line = ' ' * (prev_indent + 4) + stripped
                        else:
                            fixed_line = ' ' * prev_indent + stripped
                        break
        
        elif 'unterminated string' in err_str:
            if stripped.count('"') % 2 == 1:
                fixed_line = problem_line.rstrip() + '"'
            elif stripped.count("'") % 2 == 1:
                fixed_line = problem_line.rstrip() + "'"
        
        elif 'unmatched' in err_str and ')' in err_str:
            # Extra paren
            fixed_line = problem_line.replace(')', '', 1)
        
        elif 'invalid syntax' in err_str:
            if stripped.startswith('except '):
                # Find matching try
                for j in range(lineno - 2, max(0, lineno - 20), -1):
                    prev = lines[j]
                    if prev.strip().startswith('try:'):
                        try_indent = len(prev) - len(prev.lstrip())
                        fixed_line = ' ' * try_indent + stripped
                        break
            elif stripped.startswith('else:') or stripped.startswith('elif '):
                for j in range(lineno - 2, max(0, lineno - 20), -1):
                    prev = lines[j]
                    prev_s = prev.strip()
                    if prev_s and not prev_s.startswith('#'):
                        prev_indent = len(prev) - len(prev.lstrip())
                        fixed_line = ' ' * prev_indent + stripped
                        break
        
        if fixed_line is not None:
            lines[lineno - 1] = fixed_line
            content = '\n'.join(lines)
        else:
            p.write_text(content, encoding='utf-8')
            for idx in range(max(0, lineno-3), min(len(lines), lineno+2)):
                print(f"  {idx+1}: {lines[idx][:150]}")
            print(f"\nCannot auto-fix at line {lineno} (iteration {iteration}): {e}")
            break
