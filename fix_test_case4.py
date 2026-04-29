import pathlib

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')
lines = content.split('\n')

# Find and fix all lines with broken Chinese characters
# The replacement character U+FFFD appears as ? in the output
fixes = {
    '不存': '不存在',
    '已删': '已删除',
    '已驳': '已驳回',
    '已废': '已废弃',
    '纠正模': '纠正模式',
    '纠正失': '纠正失败',
    '提交验': '提交验证',
    '验证结': '验证结果',
    '纠正用': '纠正用例',
    '纠正状': '纠正状态',
    '工作流状': '工作流状态',
    '状态列': '状态列表',
    '状态转换请': '状态转换请求',
    '请求模': '请求模型',
    '目标状': '目标状态',
    '转换规': '转换规则',
    '评审': '评审中',
    '技术视': '技术视图',
    '技术视图编辑请求模': '技术视图编辑请求模型',
    '技术视图编辑请': '技术视图编辑请求',
    '获取技术视图失': '获取技术视图失败',
    '更新技术视图失': '更新技术视图失败',
    '步骤技术信': '步骤技术信息',
    '对应步': '对应步骤',
    '元素定位信': '元素定位信息',
    'CSS选择': 'CSS选择器',
    'XPath表达': 'XPath表达式',
    '定位信': '定位信息',
    '定位方': '定位方式',
    '版本记录不存': '版本记录不存在',
    '指定版': '指定版本',
    '无快照数据，无法恢': '无快照数据，无法恢复',
    '测试用': '测试用例',
    '批量软删': '批量软删除',
    '用户': '用户名',
    '未找': '未找到',
    '恢复完成：成': '恢复完成：成功',
    '删除完成：成': '删除完成：成功',
    '一次最多恢': '一次最多恢复',
    '一次最多删': '一次最多删除',
    '排除软删除记录': '排除软删除记录）',
    '计算偏移': '计算偏移量',
    '工作流历': '工作流历史',
    '状态已': '状态已从',
    '纠正': '纠正中',
    '验证': '验证中',
}

fixed_count = 0
for i, line in enumerate(lines):
    original = line
    # Fix unterminated string literals - lines ending with broken chars inside quotes
    # Replace U+FFFD (replacement char) patterns
    import re
    # Replace any occurrence of known broken patterns
    for broken, fixed in fixes.items():
        if broken in line and line != original.replace(broken, fixed):
            line = line.replace(broken, fixed)
    
    if line != original:
        lines[i] = line
        fixed_count += 1

# Also fix lines that have unterminated strings due to broken chars at end
# Pattern: detail="xxx<broken>"  where the closing quote is on the next line
result_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check if this line has an unclosed string with broken chars
    if line.count('"') % 2 == 1 and i + 1 < len(lines):
        # This might be a line with broken string - merge with next line
        next_line = lines[i + 1].strip()
        if next_line.startswith(')') or next_line.startswith(','):
            # The string was broken - fix it
            # Remove the broken trailing chars and close the string
            fixed_line = line.rstrip()
            # Find last opening quote
            last_quote = fixed_line.rfind('"')
            if last_quote > 0:
                prefix = fixed_line[:last_quote]
                # Extract the key (like detail=) 
                if 'detail=' in prefix or 'message' in prefix:
                    # Get the content between quotes
                    content_start = prefix.rfind('"')
                    if content_start >= 0:
                        inner = prefix[content_start+1:]
                        # Clean up broken chars from inner content
                        inner_clean = inner.encode('ascii', errors='ignore').decode('ascii')
                        # If inner is mostly Chinese with broken ending, fix it
                        if '不存' in inner:
                            fixed_line = prefix[:content_start] + '"测试用例不存在"'
                        elif '已删' in inner:
                            fixed_line = prefix[:content_start] + '"测试用例已删除"'
                        elif '版本' in inner and '不存' in inner:
                            fixed_line = prefix[:content_start] + '"版本记录不存在"'
                        elif '无法恢' in inner:
                            fixed_line = prefix[:content_start] + '"该版本无快照数据，无法恢复"'
                        else:
                            # Generic fix - just close the string
                            fixed_line = prefix[:content_start+1] + inner_clean + '"'
            result_lines.append(fixed_line)
            i += 1
            continue
    result_lines.append(line)
    i += 1

content = '\n'.join(result_lines)
p.write_text(content, encoding='utf-8')
print(f'Fixed {fixed_count} lines')
