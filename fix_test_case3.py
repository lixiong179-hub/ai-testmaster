import pathlib
import re

p = pathlib.Path(r'd:\PythonFile\ai-testmaster\app\api\v1\endpoints\test_case.py')
content = p.read_text(encoding='utf-8', errors='replace')

# Fix all unterminated string patterns where Chinese chars were truncated
# Pattern: detail="xxx?"  -> detail="xxx在"  or detail="xxx")
# The ? is the replacement character for broken multi-byte UTF-8

# Fix detail strings that end with broken chars
content = re.sub(r'detail="测试用例不存.{0,3}"', 'detail="测试用例不存在"', content)
content = re.sub(r'detail="版本记录不存.{0,3}"', 'detail="版本记录不存在"', content)
content = re.sub(r'detail=f"AI服务认证失败:.{0,30}"', 'detail=f"AI服务认证失败: {e.message}。请检查.env 文件中的 DEEPSEEK_API_KEY 是否正确"', content)
content = re.sub(r'detail=f"AI服务请求频率过高:.{0,30}"', 'detail=f"AI服务请求频率过高: {e.message}。请稍后重试"', content)
content = re.sub(r'detail=f"AI服务请求超时:.{0,30}"', 'detail=f"AI服务请求超时: {e.message}。请稍后重试"', content)
content = re.sub(r'detail=f"AI响应格式错误:.{0,30}"', 'detail=f"AI响应格式错误: {e.message}。请稍后重试或联系管理员"', content)
content = re.sub(r'detail=f"AI响应解析失败:.{0,30}"', 'detail=f"AI响应解析失败: {e.message}。请稍后重试或联系管理员"', content)
content = re.sub(r'detail=f"工作流状态转换失.{0,3}"', 'detail=f"工作流状态转换失败: {str(e)}"', content)
content = re.sub(r'detail=f"开始纠正失.{0,3}"', 'detail=f"开始纠正失败: {str(e)}"', content)
content = re.sub(r'detail=f"获取技术视图失.{0,3}"', 'detail=f"获取技术视图失败: {str(e)}"', content)
content = re.sub(r'detail=f"更新技术视图失.{0,3}"', 'detail=f"更新技术视图失败: {str(e)}"', content)
content = re.sub(r'detail="该版本无快照数据.{0,20}"', 'detail="该版本无快照数据，无法恢复"', content)
content = re.sub(r'detail=f"不允许从.{0,100}转换.{0,5}"', 'detail=f"不允许从当前状态转换到目标状态"', content)
content = re.sub(r'detail=f"当前状态为.{0,50}才能提交验.{0,5}"', 'detail=f"当前状态不允许提交验证"', content)
content = re.sub(r'detail="用例正在验证中.{0,20}"', 'detail="用例正在验证中，请等待验证结果"', content)
content = re.sub(r'detail="请提供CSS选择器.{0,30}"', 'detail="请提供CSS选择器或XPath至少一种定位方式"', content)

# Fix return message strings
content = re.sub(r'"message": "测试用例已删.{0,5}"', '"message": "测试用例已删除"', content)
content = re.sub(r'"message": "已进入纠正模.{0,5}"', '"message": "已进入纠正模式"', content)
content = re.sub(r'"message": "已提交验.{0,5}"', '"message": "已提交验证"', content)
content = re.sub(r'"message": f"状态已.{0,50}转换.{0,50}"', '"message": "状态已转换"', content)

# Fix logger strings
content = re.sub(r'logger\.info\(f"\[版本恢复\].{0,100}"\)', 'logger.info(f"[版本恢复] 用户ID={current_user.id}, 用例ID={test_case_id}, 恢复到版本{version.version_number}")', content)
content = re.sub(r'logger\.info\(f"\[删除用例\].{0,100}"\)', 'logger.info(f"[删除用例] 用户ID={current_user.id}, 用户名={current_user.username}, 用例ID={test_case_id}")', content)
content = re.sub(r'logger\.error\(f"获取技术视图失.{0,20}"\)', 'logger.error(f"获取技术视图失败: {e}")', content)
content = re.sub(r'logger\.error\(f"更新技术视图失.{0,20}"\)', 'logger.error(f"更新技术视图失败: {e}")', content)
content = re.sub(r'logger\.error\(f"工作流状态转换失.{0,20}"\)', 'logger.error(f"工作流状态转换失败: {e}")', content)
content = re.sub(r'logger\.error\(f"开始纠正失.{0,20}"\)', 'logger.error(f"开始纠正失败: {e}")', content)

# Fix comment lines with broken chars
content = re.sub(r'# 构建查询（排除软删除记录.{0,5}', '# 构建查询（排除软删除记录）', content)
content = re.sub(r'# 计算偏移.{0,5}', '# 计算偏移量', content)
content = re.sub(r'# 批量操作路由（必须放.{0,50}拦截.{0,5}', '# 批量操作路由（必须放在/{test_case_id} 之前，避免被路径参数拦截）', content)
content = re.sub(r'# 批量软删.{0,5}', '# 批量软删除', content)
content = re.sub(r'# 先删除旧的步.{0,5}', '# 先删除旧的步骤', content)
content = re.sub(r'# 添加新步.{0,5}', '# 添加新步骤', content)
content = re.sub(r'# 同时更新TestStep表中的数.{0,5}', '# 同时更新TestStep表中的数据', content)
content = re.sub(r'# 返回字典格式，保持与技术视图一.{0,5}', '# 返回字典格式，保持与技术视图一致', content)
content = re.sub(r'# 验证描述不为.{0,5}', '# 验证描述不为空', content)
content = re.sub(r'# 创建测试步骤 - 兼容不同格式的步骤数.{0,5}', '# 创建测试步骤 - 兼容不同格式的步骤数据', content)
content = re.sub(r'# 处理不同格式的步骤数.{0,5}', '# 处理不同格式的步骤数据', content)
content = re.sub(r'# 检查是否已有定位信.{0,5}', '# 检查是否已有定位信息', content)
content = re.sub(r'# 创建新定位信.{0,5}', '# 创建新定位信息', content)
content = re.sub(r'# 更新步骤技术信.{0,5}', '# 更新步骤技术信息', content)
content = re.sub(r'# 同步更新steps_json中对应步.{0,5}', '# 同步更新steps_json中对应步骤', content)
content = re.sub(r'# 返回更新后的技术视.{0,5}', '# 返回更新后的技术视图', content)
content = re.sub(r'# 验证至少有一个定位方.{0,5}', '# 验证至少有一个定位方式', content)

# Fix docstrings
content = re.sub(r'""".*恢复测试用例到指定版.{0,10}"""', '"""恢复测试用例到指定版本"""', content)
content = re.sub(r'""".*删除测试用例（软删除.{0,10}"""', '"""删除测试用例（软删除）"""', content)
content = re.sub(r'""".*获取测试用例技术视.{0,10}"""', '"""获取测试用例技术视图"""', content)
content = re.sub(r'""".*获取用例纠正状.{0,10}"""', '"""获取用例纠正状态"""', content)
content = re.sub(r'""".*开始纠正用.{0,10}"""', '"""开始纠正用例"""', content)
content = re.sub(r'""".*技术视图编辑请求模.{0,10}"""', '"""技术视图编辑请求模型"""', content)
content = re.sub(r'""".*工作流状态转换请求模.{0,10}"""', '"""工作流状态转换请求模型"""', content)
content = re.sub(r'""".*获取测试用例工作流状.{0,10}"""', '"""获取测试用例工作流状态"""', content)
content = re.sub(r'""".*转换测试用例工作流状.{0,10}"""', '"""转换测试用例工作流状态"""', content)
content = re.sub(r'""".*更新测试用例技术视.{0,10}"""', '"""更新测试用例技术视图"""', content)

# Fix f-string with broken chars in log lines
content = re.sub(r'f"\[批量恢复\].{0,200}"', 'f"[批量恢复] 用户ID={current_user.id}, 用户名={current_user.username}, 恢复用例IDs={restored_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"', content)
content = re.sub(r'f"\[批量删除\].{0,200}"', 'f"[批量删除] 用户ID={current_user.id}, 用户名={current_user.username}, 删除用例IDs={deleted_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"', content)
content = re.sub(r'f"状.{0,5} {old_status} -> {request.target_status}.{0,50}"', 'f"状态: {old_status} -> {request.target_status}, 备注: {request.comment or 无}"', content)

# Fix broken raise ValueError
content = re.sub(r"raise ValueError\(f'一次最多恢.{0,10}'\)", "raise ValueError(f'一次最多恢复200个用例，当前: {len(v)}')", content)
content = re.sub(r"raise ValueError\(f'一次最多删.{0,10}'\)", "raise ValueError(f'一次最多删除200个用例，当前: {len(v)}')", content)
content = re.sub(r"raise ValueError\(f'无效的目标状.{0,30}'\)", "raise ValueError(f'无效的目标状态: {v}，有效值为: {valid_statuses}')", content)
content = re.sub(r"raise ValueError\(f'步骤数量不能超过200.{0,20}'\)", "raise ValueError(f'步骤数量不能超过200，当前: {len(v)}')", content)
content = re.sub(r"raise ValueError\('描述不能为空且至少需.{0,20}'\)", "raise ValueError('描述不能为空且至少需要5个字符')", content)
content = re.sub(r"raise ValueError\(f'描述过长.{0,30}'\)", "raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')", content)

# Fix remaining broken patterns
content = re.sub(r"raise HTTPException\(status_code=status.HTTP_404_NOT_FOUND, detail=\"测试用例不存.{0,5}\"\)", "raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=\"测试用例不存在\")", content)
content = re.sub(r"raise HTTPException\(status_code=status.HTTP_404_NOT_FOUND, detail=\"版本记录不存.{0,5}\"\)", "raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=\"版本记录不存在\")", content)

# Fix broken dict entries
content = re.sub(r"'correction_status_label': CORRECTION_STATUS_LABELS.get\(current_status, '.{0,5}'\)", "'correction_status_label': CORRECTION_STATUS_LABELS.get(current_status, '未知')", content)

# Fix status labels dict
content = re.sub(r"'review': '评审.{0,5}'", "'review': '评审中'", content)
content = re.sub(r"'rejected': '已驳.{0,5}'", "'rejected': '已驳回'", content)
content = re.sub(r"'deprecated': '已废.{0,5}'", "'deprecated': '已废弃'", content)
content = re.sub(r"'correcting': '纠正.{0,5}'", "'correcting': '纠正中'", content)
content = re.sub(r"'verifying': '验证.{0,5}'", "'verifying': '验证中'", content)

# Fix remaining broken return message
content = re.sub(r'return \{"message": "测试用例已删.{0,5}\}', 'return {"message": "测试用例已删除"}', content)

# Fix broken comment about test data
content = re.sub(r'为测试步骤添加元素定位信.{0,10}', '为测试步骤添加元素定位信息', content)

# Fix broken multiline strings - join lines that were incorrectly split
content = re.sub(r'f"恢复完成：成.{0,5}\{success_count\} 个，失败 \{fail_count\} 个，未找.{0,5}\{len\(not_found_ids\)\} .{0,5}"', r'f"恢复完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"', content)
content = re.sub(r'f"删除完成：成.{0,5}\{success_count\} 个，失败 \{fail_count\} 个，未找.{0,5}\{len\(not_found_ids\)\} .{0,5}"', r'f"删除完成：成功{success_count} 个，失败 {fail_count} 个，未找到{len(not_found_ids)} 个"', content)

p.write_text(content, encoding='utf-8')
print('Comprehensive fix done')
