import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')
R = '\ufffd'

# Precise line-by-line replacements based on the scan results
replacements = {
    f"raise ValueError(f'一次最多恢{R}00个用例，当前: {{len(v)}}')": "raise ValueError(f'一次最多恢复200个用例，当前: {len(v)}')",
    f"未找{R}{{len(not_found_ids)}": "未找到{len(not_found_ids)}",
    f"raise ValueError(f'一次最多删{R}00个用例，当前: {{len(v)}}')": "raise ValueError(f'一次最多删除200个用例，当前: {len(v)}')",
    f"批量删除测试用例（软删除{R}": "批量删除测试用例（软删除）",
    f'detail="测试用例不存{R}': 'detail="测试用例不存在"',
    f'"""删除测试用例（软删除{R}"""': '"""删除测试用例（软删除）"""',
    f'"""获取测试用例技术视{R}"""': '"""获取测试用例技术视图"""',
    f'detail=f"获取技术视图失{R} {{str(e)}}"': 'detail=f"获取技术视图失败: {str(e)}"',
    f"raise ValueError('描述不能为空且至少需{R}0个字{R})": "raise ValueError('描述不能为空且至少需要10个字符')",
    f'detail="项目不存{R}': 'detail="项目不存在"',
    f'detail="描述不能为空且至少需{R}0个字{R}': 'detail="描述不能为空且至少需要10个字符"',
    f'detail=f"AI服务认证失败: {{e.message}}。请检{R}.env 文件中的 DEEPSEEK_API_KEY 是否正确{R}': 'detail=f"AI服务认证失败: {e.message}。请检查.env 文件中的 DEEPSEEK_API_KEY 是否正确"',
    f'detail=f"AI服务请求频率过高: {{e.message}}。请稍后重试{R}': 'detail=f"AI服务请求频率过高: {e.message}。请稍后重试"',
    f'detail=f"AI服务请求超时: {{e.message}}。请稍后重试{R}': 'detail=f"AI服务请求超时: {e.message}。请稍后重试"',
    f'detail=f"AI响应格式错误: {{e.message}}。请稍后重试或联系管理员{R}': 'detail=f"AI响应格式错误: {e.message}。请稍后重试或联系管理员"',
    f'detail=f"AI响应解析失败: {{e.message}}。请稍后重试或联系管理员{R}': 'detail=f"AI响应解析失败: {e.message}。请稍后重试或联系管理员"',
}

for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {old[:50]}...")

# Now handle remaining broken lines by scanning for U+FFFD
lines = content.split('\n')
fixed_lines = []
for i, line in enumerate(lines):
    if R in line:
        # Generic fixes based on context
        if 'detail=' in line and '不存' in line:
            line = line.replace(f'不存{R}', '不存在')
            if line.count('"') % 2 == 1:
                line = line.rstrip() + '"'
        elif 'detail=' in line and '已删' in line:
            line = line.replace(f'已删{R}', '已删除')
            if line.count('"') % 2 == 1:
                line = line.rstrip() + '"'
        elif 'detail=' in line and '失' in line:
            line = line.replace(f'失{R}', '失败')
            if line.count('"') % 2 == 1:
                line = line.rstrip() + '"'
        elif '"""' in line:
            line = line.replace(R, '）')
        elif 'message' in line:
            line = line.replace(R, '')
            if line.count('"') % 2 == 1:
                line = line.rstrip() + '"'
        elif 'logger' in line:
            line = line.replace(R, '')
        elif '#' in line:
            line = line.replace(R, '')
        else:
            line = line.replace(R, '')
            if line.count('"') % 2 == 1:
                line = line.rstrip() + '"'
    fixed_lines.append(line)

content = '\n'.join(fixed_lines)
p.write_text(content, encoding='utf-8')

# Verify syntax
import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Still has syntax error: {e}")
