"""深度诊断：为什么extract返回0个测试点"""
import requests
import json
import sys
import asyncio

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

async def test_ai_directly():
    """直接调用AI客户端测试"""
    print("=" * 70)
    print("  深度诊断：AI提取测试点过程")
    print("=" * 70)

    from app.utils.ai_client import ai_client
    from app.services.file_content_extractor import FileContentExtractor
    from app.db.database import PrimarySessionLocal
    from app.models.project import ProjectFile

    # 1. 获取文件内容
    print("\n[1/4] 提取文件内容...")
    db = PrimarySessionLocal()
    try:
        file_record = db.query(ProjectFile).filter(ProjectFile.id == 1).first()

        if not file_record:
            print("  ❌ 文件ID=1不存在")
            return

        print(f"  文件名: {file_record.file_name}")
        print(f"  文件类型: {file_record.file_type}")
        print(f"  文件URL: {file_record.file_url}")

        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(file_record, force_refresh=False)

        if not result.get("success"):
            print(f"  ❌ 文件内容提取失败: {result.get('error')}")
            return

        content = result.get("content", "")
        print(f"  ✅ 内容长度: {len(content)} 字符")

        if not content:
            print("  ⚠️  内容为空！这就是返回0个测试点的原因")
            print("     → 文件可能无法解析或文件已损坏")
            return

        print(f"  内容预览 (前200字):")
        print(f"  {'─' * 50}")
        print(f"  {content[:200]}...")
        print(f"  {'─' * 50}")

    finally:
        db.close()

    # 2. 直接调用AI分析
    print("\n[2/4] 调用AI分析（观察完整响应）...")
    try:
        chunk_count = 0
        has_data_chunk = False
        final_content = ""

        async for chunk in ai_client.analyze_requirements_stream(content):
            chunk_count += 1
            print(f"\n  📦 Chunk #{chunk_count}:")

            if "progress" in chunk:
                print(f"     进度: {chunk.get('progress')}%")
                print(f"     消息: {chunk.get('message', '')}")

            if "data" in chunk:
                has_data_chunk = True
                data = chunk["data"]
                print(f"     🎯 发现数据! 类型: {type(data)}, 长度: {len(data) if isinstance(data, list) else 'N/A'}")

                if isinstance(data, list) and len(data) > 0:
                    print(f"\n     ✅ 成功提取到 {len(data)} 个测试点:")
                    for i, item in enumerate(data[:3], 1):
                        print(f"       {i}. [{item.get('module', '?')}] {item.get('point', '?')[:50]}")
                    if len(data) > 3:
                        print(f"       ... 还有 {len(data) - 3} 个")
                else:
                    print(f"     ⚠️  数据为空列表")

        print(f"\n  总共收到 {chunk_count} 个chunk")
        print(f"  是否收到data chunk: {'是 ✓' if has_data_chunk else '否 ✗'}")

        if not has_data_chunk:
            print("\n  🔍 问题定位:")
            print("     AI流式响应完成了，但没有yield包含'data'的chunk")
            print("     这意味着:")
            print("     ① AI返回的内容无法解析为JSON")
            print("     ② AI返回了空内容")
            print("     ③ 解析逻辑有bug")

    except Exception as e:
        print(f"\n  ❌ AI调用异常: {e}")
        import traceback
        traceback.print_exc()

    # 3. 测试简单内容
    print("\n\n[3/4] 用简单测试内容验证AI是否正常工作...")
    test_content = """
    用户管理系统需求：

    1. 用户注册功能
    - 支持邮箱和手机号注册
    - 密码强度校验
    - 发送验证邮件

    2. 用户登录功能
    - 支持账号密码登录
    - 支持短信验证码登录
    - 记住登录状态
    """

    try:
        print(f"  测试内容长度: {len(test_content)}")

        async for chunk in ai_client.analyze_requirements_stream(test_content):
            if "data" in chunk:
                data = chunk["data"]
                if isinstance(data, list):
                    print(f"  ✅ 简单内容测试成功! 提取到 {len(data)} 个测试点")
                    for item in data[:2]:
                        print(f"     - {item.get('point', '?')}")
                    return
                break

        print("  ⚠️  简单内容也没有返回data，可能是AI服务问题")

    except Exception as e:
        print(f"  ❌ 测试失败: {e}")

    # 4. 总结
    print("\n" + "=" * 70)
    print("  诊断总结")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_ai_directly())
