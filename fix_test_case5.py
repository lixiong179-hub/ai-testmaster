import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Strategy: find all lines with U+FFFD replacement character and fix them
# U+FFFD is the Unicode replacement character that appears when UTF-8 is corrupted
replacement_char = '\ufffd'

lines_with_issues = []
for i, line in enumerate(content.split('\n')):
    if replacement_char in line:
        lines_with_issues.append((i+1, line))

print(f"Found {len(lines_with_issues)} lines with broken characters")
for lineno, line in lines_with_issues[:20]:
    print(f"  Line {lineno}: {line[:100]}")
