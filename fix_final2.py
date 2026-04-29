import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Remove ALL U+FFFD replacement characters and fix the surrounding context
# Strategy: replace U+FFFD with appropriate Chinese character based on context

import re

# First pass: fix known multi-character patterns that contain U+FFFD
R = '\ufffd'

# Fix patterns where the replacement char truncates a Chinese word
patterns = [
    # Common word completions
    (R + '00个用例', '200个用例'),
    (R + '0个字' + R, '10个字符'),
    ('不存' + R, '不存在'),
    ('已删' + R + '}', '已删除}'),
    ('已删' + R, '已删除'),
    ('已驳' + R, '已驳回'),
    ('已废' + R, '已废弃'),
    ('软删除' + R, '软删除）'),
    ('技术视' + R, '技术视图'),
    ('纠正模' + R, '纠正模式'),
    ('纠正失' + R, '纠正失败'),
    ('提交验' + R, '提交验证'),
    ('验证结' + R, '验证结果'),
    ('纠正用' + R, '纠正用例'),
    ('纠正状' + R, '纠正状态'),
    ('工作流状' + R, '工作流状态'),
    ('状态列' + R, '状态列表'),
    ('工作流历' + R, '工作流历史'),
    ('状态转换请' + R, '状态转换请求'),
    ('请求模' + R, '请求模型'),
    ('目标状' + R, '目标状态'),
    ('转换规' + R, '转换规则'),
    ('步骤技术信' + R, '步骤技术信息'),
    ('对应步' + R, '对应步骤'),
    ('元素定位信' + R, '元素定位信息'),
    ('定位信' + R, '定位信息'),
    ('定位方' + R, '定位方式'),
    ('版本记录不存' + R, '版本记录不存在'),
    ('指定版' + R, '指定版本'),
    ('无法恢' + R, '无法恢复'),
    ('批量软删' + R, '批量软删除'),
    ('未找' + R, '未找到'),
    ('恢复完成：成' + R, '恢复完成：成功'),
    ('删除完成：成' + R, '删除完成：成功'),
    ('一次最多恢' + R, '一次最多恢复'),
    ('一次最多删' + R, '一次最多删除'),
    ('排除软删除记录' + R, '排除软删除记录）'),
    ('计算偏移' + R, '计算偏移量'),
    ('状态已' + R, '状态已从'),
    ('获取技术视图失' + R, '获取技术视图失败'),
    ('更新技术视图失' + R, '更新技术视图失败'),
    ('开始纠正失' + R, '开始纠正失败'),
    ('工作流状态转换失' + R, '工作流状态转换失败'),
    ('技术视图编辑请求模' + R, '技术视图编辑请求模型'),
    ('技术视图编辑请' + R, '技术视图编辑请求'),
    ('测试用' + R, '测试用例'),
    ('项目不存' + R, '项目不存在'),
    ('检' + R + '.env', '检查.env'),
    ('是否正确' + R, '是否正确）'),
    ('稍后重试' + R, '稍后重试）'),
    ('联系管理员' + R, '联系管理员）'),
    ('评审' + R, '评审中'),
    ('纠正' + R, '纠正中'),
    ('验证' + R, '验证中'),
    ('必须放' + R, '必须放在'),
    ('避免被路径参数拦截' + R, '避免被路径参数拦截）'),
    ('步' + R, '步骤'),
    ('数据' + R, '数据'),
    ('版本' + R, '版本'),
    ('用户' + R, '用户名'),
    ('一' + R, '一致'),
]

for old, new in patterns:
    content = content.replace(old, new)

# Second pass: remove any remaining U+FFFD characters
content = content.replace(R, '')

# Fix any resulting empty strings or broken quotes
# Fix lines like detail="" (empty detail)
content = content.replace('detail=""', 'detail="未知错误"')

# Fix unterminated f-strings that lost their closing quote
lines = content.split('\n')
fixed_lines = []
for line in lines:
    # Count unescaped double quotes
    quote_count = 0
    in_escape = False
    for ch in line:
        if ch == '\\' and not in_escape:
            in_escape = True
            continue
        if ch == '"' and not in_escape:
            quote_count += 1
        in_escape = False
    
    if quote_count % 2 == 1:
        # Odd number of quotes - likely broken
        # Add closing quote at end if it looks like a detail/message line
        stripped = line.rstrip()
        if ('detail=' in stripped or 'message' in stripped) and not stripped.endswith('"'):
            line = stripped + '"'
    
    fixed_lines.append(line)

content = '\n'.join(fixed_lines)
p.write_text(content, encoding='utf-8')

# Verify
import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Syntax error: {e}")
