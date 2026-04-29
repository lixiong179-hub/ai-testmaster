"""自测：验证Web端对比示例和前置条件规则"""
import sys
sys.path.insert(0, ".")

files = {
    "ai_client_test_case.py": "app/utils/ai_client_test_case.py",
    "ai_client_stream.py": "app/utils/ai_client_stream.py",
    "ai_client_enhanced.py": "app/utils/ai_client_enhanced.py",
    "ai_prompt_mixin.py": "app/services/case_generation/ai_prompt_mixin.py",
    "case_prompt.py": "app/services/prompt_builder/case_prompt.py",
    "ai_prompt_builder.py": "app/services/test_case_generation/ai_prompt_builder.py",
    "linear_prompt.py": "app/services/prompt_builder/linear_prompt.py",
    "case_generation_prompt_builder.py": "app/services/case_generation_prompt_builder.py",
    "xmind_ai_parser.py": "app/services/xmind_ai_parser.py",
}

all_pass = True
for name, path in files.items():
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查1: Web端对比示例
    has_web_example = "对比6-Web端表单" in content
    has_web_bad = "测试后台用户创建功能" in content
    has_web_good = "浏览器网络正常" in content

    # 检查2: 前置条件规则区分Web/App
    has_web_app_distinction = "Web端写" in content and "App端写" in content

    # 检查3: 6对对比
    has_6_pairs = all(f"【对比{i}" in content for i in range(1, 7))

    ok = has_web_example and has_web_bad and has_web_good and has_web_app_distinction and has_6_pairs
    status = "✅" if ok else "❌"
    if not ok: all_pass = False

    details = []
    if not has_web_example: details.append("缺Web端对比示例")
    if not has_web_app_distinction: details.append("前置条件未区分Web/App")
    if not has_6_pairs: details.append("缺6对对比")
    detail_str = f" ({', '.join(details)})" if details else ""
    print(f"  {status} {name}{detail_str}")

# 检查 build_project_env_info
with open("app/utils/ai_client_prompt.py", "r", encoding="utf-8") as f:
    content = f.read()
has_dynamic = "浏览器网络正常" in content and "设备网络正常" in content
has_old = "系统已通过配置自动登录至目标页面" in content
status = "✅" if has_dynamic and not has_old else "❌"
if not (has_dynamic and not has_old): all_pass = False
detail = ""
if not has_dynamic: detail = " (缺动态环境适配)"
if has_old: detail = " (残留旧规则)"
print(f"  {status} ai_client_prompt.py{detail}")

print()
if all_pass:
    print("🎉 全部通过！Web端偏置已消除，前置条件规则已适配项目类型")
else:
    print("⚠️ 存在问题")
    sys.exit(1)
