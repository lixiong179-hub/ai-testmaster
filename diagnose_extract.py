"""测试点提取失败 - 诊断工具"""
import sys
import os

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("  测试点提取功能诊断工具")
print("=" * 70)

# 1. 检查环境变量配置
print("\n[1/5] 检查AI API配置...")
try:
    from app.core.config import settings

    if hasattr(settings, 'DEEPSEEK_API_KEY'):
        api_key = settings.DEEPSEEK_API_KEY
        if api_key and len(api_key) > 10:
            print(f"  ✅ DEEPSEEK_API_KEY: 已配置 (长度: {len(api_key)})")
        elif api_key:
            print(f"  ⚠️  DEEPSEEK_API_KEY: 已配置但可能无效 (长度: {len(api_key)})")
        else:
            print(f"  ❌ DEEPSEEK_API_KEY: 未配置（空值）")
            print("     → 这是导致提取失败的**主要原因**！")

    if hasattr(settings, 'DEEPSEEK_API_URL'):
        print(f"  ✅ DEEPSEEK_API_URL: {settings.DEEPSEEK_API_URL}")

    if hasattr(settings, 'DEEPSEEK_MODEL'):
        print(f"  ✅ DEEPSEEK_MODEL: {settings.DEEPSEEK_MODEL}")

except Exception as e:
    print(f"  ❌ 配置加载失败: {e}")

# 2. 检查ai_client模块
print("\n[2/5] 检查AI客户端模块...")
try:
    from app.utils.ai_client import ai_client
    print(f"  ✅ ai_client 模块加载成功")
    print(f"     类型: {type(ai_client).__name__}")

    if hasattr(ai_client, 'api_key'):
        key = ai_client.api_key
        if key:
            print(f"  ✅ API Key已注入到客户端 (前4位: {key[:4]}...)")
        else:
            print(f"  ❌ API Key未注入到客户端")

except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
except Exception as e:
    print(f"  ❌ 初始化失败: {e}")

# 3. 检查extract函数
print("\n[3/5] 检查extract_test_points_from_content函数...")
try:
    from app.services.ai_analysis_service import extract_test_points_from_content
    print(f"  ✅ 函数导入成功")

    # 查看函数签名
    import inspect
    sig = inspect.signature(extract_test_points_from_content)
    print(f"     签名: extract_test_points_from_content{sig}")

except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
    print("     → 这会导致500错误 'not defined'")
except Exception as e:
    print(f"  ❌ 错误: {e}")

# 4. 测试API连接（如果有密钥）
print("\n[4/5] 测试DeepSeek API连接...")
try:
    from app.core.config import settings

    if not settings.DEEPSEEK_API_KEY:
        print("  ⏭️  跳过：未配置API密钥")
    else:
        import requests
        resp = requests.post(
            settings.DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5
            },
            timeout=10
        )

        if resp.status_code == 200:
            print(f"  ✅ API连接成功！")
        elif resp.status_code == 401:
            print(f"  ❌ API认证失败 (401): API密钥无效或已过期")
        elif resp.status_code == 429:
            print(f"  ⚠️  API频率限制 (429): 请求太频繁")
        else:
            print(f"  ⚠️  API返回: HTTP {resp.status_code}")
            print(f"     响应: {resp.text[:100]}")

except Exception as e:
    print(f"  ❌ 连接测试失败: {e}")

# 5. 总结和建议
print("\n[5/5] 诊断总结")
print("-" * 70)

issues = []
solutions = []

# 检查.env文件
env_file = '.env'
if os.path.exists(env_file):
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'DEEPSEEK_API_KEY=' in content and 'DEEPSEEK_API_KEY=your_' in content:
            issues.append("DEEPSEEK_API_KEY 使用了占位符值")
            solutions.append("请将 .env 文件中的 DEEPSEEK_API_KEY 替换为真实的API密钥")
        elif 'DEEPSEEK_API_KEY=\n' in content or 'DEEPSEEK_API_KEY=$' in content or content.endswith('DEEPSEEK_API_KEY='):
            issues.append("DEEPSEEK_API_KEY 为空")
            solutions.append("请在 .env 文件第27行填入你的 DeepSeek API 密钥")
else:
    issues.append(".env 文件不存在")
    solutions.append("请创建 .env 文件并配置 DEEPSEEK_API_KEY")

if issues:
    print("\n❌ 发现以下问题:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")

    print("\n✅ 解决方案:")
    for i, solution in enumerate(solutions, 1):
        print(f"  {i}. {solution}")

    print("\n📝 详细步骤:")
    print("""
  步骤1: 获取DeepSeek API密钥
    ┌─────────────────────────────────────────────┐
    │  访问 https://platform.deepseek.com/         │
    │  注册账号 → 创建API Key → 复制密钥          │
    └─────────────────────────────────────────────┘

  步骤2: 配置.env文件
  ┌─────────────────────────────────────────────┐
    # 编辑 .env 文件第27行
    DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx  ← 粘贴你的密钥
  └─────────────────────────────────────────────┘

  步骤3: 重启后端服务
  ┌─────────────────────────────────────────────┐
    # 停止当前后端服务，然后重新启动
    $ python -m uvicorn app.main:app --port 8000
  └─────────────────────────────────────────────┘

  步骤4: 再次测试提取功能
    """)
else:
    print("\n✅ 所有检查通过！如果仍然失败，请查看后端日志获取详细错误信息")

print("\n" + "=" * 70)
