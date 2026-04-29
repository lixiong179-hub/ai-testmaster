import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

lines = content.split('\n')
fixed = 0
for i, line in enumerate(lines):
    if 'message' in line and 'success_count' in line and 'fail_count' in line and 'restoredIds' in lines[i-2] if i >= 2 else False:
        lines[i] = '        "message": f"恢复完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"'
        fixed += 1
    elif 'message' in line and 'success_count' in line and 'fail_count' in line and 'deleted_case_ids' in lines[i-2] if i >= 2 else False:
        lines[i] = '        "message": f"删除完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"'
        fixed += 1

content = '\n'.join(lines)

# Fix remaining broken patterns with regex
import re
content = re.sub(
    r'f"恢复完成：成.{0,3}\{success_count\} 个，失败 \{fail_count\} 个，未找.{0,3}\{len\(not_found_ids\)\} .{0,3}"',
    r'f"恢复完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"',
    content
)
content = re.sub(
    r'f"删除完成：成.{0,3}\{success_count\} 个，失败 \{fail_count\} 个，未找.{0,3}\{len\(not_found_ids\)\} .{0,3}"',
    r'f"删除完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"',
    content
)

p.write_text(content, encoding='utf-8')
print(f'Fixed {fixed} lines')
