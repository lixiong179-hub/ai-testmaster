import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix ALL remaining broken patterns - comprehensive list
# Pattern: Chinese word truncated with ? (U+FFFD replacement char or literal ?)
fixes = [
    # ValueError strings
    ("raise ValueError('描述不能为空且至少需?0个字?)", "raise ValueError('描述不能为空且至少需要10个字符')"),
    ("raise ValueError(f'描述过长({{len(v)}}字符)，最大允?0000字符?)", "raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')"),
    # detail strings
    ('detail="描述不能为空且至少需?0个字?', 'detail="描述不能为空且至少需要10个字符"'),
    ('detail="项目不存?', 'detail="项目不存在"'),
    # More detail strings
    ('detail=f"不允许从', 'detail=f"不允许从'),
    # Fix broken single-line patterns where comment and code merged
    ('# 构建查询（排除软删除记录?    query =', '# 构建查询（排除软删除记录）\n    query ='),
    ('# 计算偏移?    offset =', '# 计算偏移量\n    offset ='),
    ('# 批量操作路由（必须放?/{test_case_id} 之前，避免被路径参数拦截?', '# 批量操作路由（必须放在/{test_case_id} 之前，避免被路径参数拦截）'),
    ('# 返回字典格式，保持与技术视图一?        return', '# 返回字典格式，保持与技术视图一致\n        return'),
    ('# 验证描述不为?    if not', '# 验证描述不为空\n    if not'),
    ('# 创建测试步骤 - 兼容不同格式的步骤数据?        for', '# 创建测试步骤 - 兼容不同格式的步骤数据\n        for'),
    ('# 处理不同格式的步骤数据?            if "action"', '# 处理不同格式的步骤数据\n            if "action"'),
    ('# 检查是否已有定位信息?        existing_locator', '# 检查是否已有定位信息\n        existing_locator'),
    ('# 创建新定位信息?            new_locator', '# 创建新定位信息\n            new_locator'),
    ('# 更新步骤技术信息?        if request.steps', '# 更新步骤技术信息\n        if request.steps'),
    ('# 同步更新steps_json中对应步骤?                    for idx', '# 同步更新steps_json中对应步骤\n                    for idx'),
    ('# 返回更新后的技术视图?        service', '# 返回更新后的技术视图\n        service'),
    ('# 验证至少有一个定位方式?    if not css_selector', '# 验证至少有一个定位方式\n    if not css_selector'),
]

for old, new in fixes:
    content = content.replace(old, new)

# Fix remaining ? characters that are clearly broken Chinese
# Use regex to find patterns like "需?0" -> "需要10"
content = re.sub(r'至少需?0个字?', '至少需要10个字符', content)
content = re.sub(r'最大允?0000字符?', '最大允许10000字符', content)
content = re.sub(r'一次最多恢?00', '一次最多恢复200', content)
content = re.sub(r'一次最多删?00', '一次最多删除200', content)

# Fix remaining broken detail strings
content = re.sub(r'detail="测试用例不存[^"]*"', 'detail="测试用例不存在"', content)
content = re.sub(r'detail="版本记录不存[^"]*"', 'detail="版本记录不存在"', content)
content = re.sub(r'detail="项目不存[^"]*"', 'detail="项目不存在"', content)
content = re.sub(r'detail="该版本无快照数据[^"]*"', 'detail="该版本无快照数据，无法恢复"', content)
content = re.sub(r'detail="用例正在验证中[^"]*"', 'detail="用例正在验证中，请等待验证结果"', content)
content = re.sub(r'detail="请提供CSS选择器[^"]*"', 'detail="请提供CSS选择器或XPath至少一种定位方式"', content)

# Fix broken f-string detail lines
content = re.sub(r'detail=f"获取技术视图失[^"]*"', 'detail=f"获取技术视图失败: {str(e)}"', content)
content = re.sub(r'detail=f"更新技术视图失[^"]*"', 'detail=f"更新技术视图失败: {str(e)}"', content)
content = re.sub(r'detail=f"工作流状态转换失[^"]*"', 'detail=f"工作流状态转换失败: {str(e)}"', content)
content = re.sub(r'detail=f"开始纠正失[^"]*"', 'detail=f"开始纠正失败: {str(e)}"', content)
content = re.sub(r'detail=f"AI服务认证失败[^"]*"', 'detail=f"AI服务认证失败: {e.message}。请检查.env 文件中的 DEEPSEEK_API_KEY 是否正确"', content)
content = re.sub(r'detail=f"AI服务请求频率过高[^"]*"', 'detail=f"AI服务请求频率过高: {e.message}。请稍后重试"', content)
content = re.sub(r'detail=f"AI服务请求超时[^"]*"', 'detail=f"AI服务请求超时: {e.message}。请稍后重试"', content)
content = re.sub(r'detail=f"AI响应格式错误[^"]*"', 'detail=f"AI响应格式错误: {e.message}。请稍后重试或联系管理员"', content)
content = re.sub(r'detail=f"AI响应解析失败[^"]*"', 'detail=f"AI响应解析失败: {e.message}。请稍后重试或联系管理员"', content)

# Fix broken return messages
content = re.sub(r'"message": "测试用例已删[^"]*"', '"message": "测试用例已删除"', content)
content = re.sub(r'"message": "已进入纠正模[^"]*"', '"message": "已进入纠正模式"', content)
content = re.sub(r'"message": "已提交验[^"]*"', '"message": "已提交验证"', content)

# Fix broken docstrings
content = re.sub(r'""".*删除测试用例（软删除[^"]*"""', '"""删除测试用例（软删除）"""', content)
content = re.sub(r'""".*获取测试用例技术视[^"]*"""', '"""获取测试用例技术视图"""', content)
content = re.sub(r'""".*获取用例纠正状[^"]*"""', '"""获取用例纠正状态"""', content)
content = re.sub(r'""".*开始纠正用[^"]*"""', '"""开始纠正用例"""', content)
content = re.sub(r'""".*技术视图编辑请求模[^"]*"""', '"""技术视图编辑请求模型"""', content)
content = re.sub(r'""".*工作流状态转换请求模[^"]*"""', '"""工作流状态转换请求模型"""', content)
content = re.sub(r'""".*获取测试用例工作流状[^"]*"""', '"""获取测试用例工作流状态"""', content)
content = re.sub(r'""".*转换测试用例工作流状[^"]*"""', '"""转换测试用例工作流状态"""', content)
content = re.sub(r'""".*更新测试用例技术视[^"]*"""', '"""更新测试用例技术视图"""', content)
content = re.sub(r'""".*恢复测试用例到指定版[^"]*"""', '"""恢复测试用例到指定版本"""', content)
content = re.sub(r'""".*批量删除测试用例（软删除[^"]*"""', '"""批量删除测试用例（软删除）"""', content)

# Fix broken ValueError
content = re.sub(r"raise ValueError\('描述不能为空且至少需[^']*\)", "raise ValueError('描述不能为空且至少需要10个字符')", content)
content = re.sub(r"raise ValueError\(f'描述过长[^']*\)", "raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')", content)
content = re.sub(r"raise ValueError\(f'一次最多恢[^']*\)", "raise ValueError(f'一次最多恢复200个用例，当前: {len(v)}')", content)
content = re.sub(r"raise ValueError\(f'一次最多删[^']*\)", "raise ValueError(f'一次最多删除200个用例，当前: {len(v)}')", content)
content = re.sub(r"raise ValueError\(f'无效的目标状[^']*\)", "raise ValueError(f'无效的目标状态: {v}，有效值为: {valid_statuses}')", content)
content = re.sub(r"raise ValueError\(f'步骤数量不能超过200[^']*\)", "raise ValueError(f'步骤数量不能超过200，当前: {len(v)}')", content)

# Fix broken status labels
content = content.replace("'review': '评审中'", "'review': '评审中'")
content = content.replace("'rejected': '已驳回'", "'rejected': '已驳回'")
content = content.replace("'deprecated': '已废弃'", "'deprecated': '已废弃'")
content = content.replace("'correcting': '纠正中'", "'correcting': '纠正中'")
content = content.replace("'verifying': '验证中'", "'verifying': '验证中'")

# Fix broken logger lines
content = re.sub(r'logger\.error\(f"获取技术视图失[^"]*"\)', 'logger.error(f"获取技术视图失败: {e}")', content)
content = re.sub(r'logger\.error\(f"更新技术视图失[^"]*"\)', 'logger.error(f"更新技术视图失败: {e}")', content)
content = re.sub(r'logger\.error\(f"工作流状态转换失[^"]*"\)', 'logger.error(f"工作流状态转换失败: {e}")', content)
content = re.sub(r'logger\.error\(f"开始纠正失[^"]*"\)', 'logger.error(f"开始纠正失败: {e}")', content)

# Fix broken f-string in log lines
content = re.sub(r'f"\[批量恢复\][^"]*"', 'f"[批量恢复] 用户ID={current_user.id}, 用户名={current_user.username}, 恢复用例IDs={restored_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"', content)
content = re.sub(r'f"\[批量删除\][^"]*"', 'f"[批量删除] 用户ID={current_user.id}, 用户名={current_user.username}, 删除用例IDs={deleted_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"', content)
content = re.sub(r'f"\[版本恢复\][^"]*"', 'f"[版本恢复] 用户ID={current_user.id}, 用例ID={test_case_id}, 恢复到版本{version.version_number}"', content)
content = re.sub(r'f"\[删除用例\][^"]*"', 'f"[删除用例] 用户ID={current_user.id}, 用户名={current_user.username}, 用例ID={test_case_id}"', content)

# Fix broken message f-strings
content = re.sub(r'f"恢复完成：成[^"]*"', r'f"恢复完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"', content)
content = re.sub(r'f"删除完成：成[^"]*"', r'f"删除完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"', content)

# Fix broken state transition message
content = re.sub(r'f"状态[^"]*转换[^"]*"', 'f"状态已从{old_status}转换到{request.target_status}"', content)

# Fix broken correction_status_label
content = re.sub(r"'correction_status_label': CORRECTION_STATUS_LABELS\.get\(current_status, '[^']*'\)", "'correction_status_label': CORRECTION_STATUS_LABELS.get(current_status, '未知')", content)

# Fix broken detail for workflow
content = re.sub(r"detail=f\"不允许从[^']*", 'detail=f"不允许从当前状态转换到目标状态"', content)
content = re.sub(r"detail=f\"当前状态为[^']*", 'detail=f"当前状态不允许提交验证"', content)

# Remove any remaining U+FFFD
content = content.replace('\ufffd', '')

p.write_text(content, encoding='utf-8')

import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"Still has error: {e}")
