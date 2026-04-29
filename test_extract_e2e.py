"""端到端测试：模拟前端完整调用流程"""
import requests
import json
import sys
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"


async def test_extract_pipeline():
    """完整测试提取管道"""
    print("=" * 70)
    print("  端到端测试：test-point/extract 完整流程")
    print("=" * 70)

    # 1. 登录
    print("\n[1] 登录...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data={
        "username": "admin", "password": "password123"
    })
    token = resp.json().get("data", {}).get("access_token")
    if not token:
        print("  ❌ 登录失败")
        return
    print(f"  ✅ 登录成功")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 通过API调用extract
    print("\n[2] 调用 /api/v1/test-point/extract (file_id=1)...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/test-point/extract",
            json={"file_id": 1},
            headers=headers,
            timeout=120
        )

        print(f"\n  HTTP状态码: {resp.status_code}")
        result = resp.json()
        print(f"  业务码: {result.get('code')}")
        print(f"  消息: {result.get('message', 'N/A')}")

        data = result.get("data", {})
        items = data.get("items", [])
        total = data.get("total", 0)

        print(f"  items数量: {len(items)}")
        print(f"  total: {total}")

        if items:
            print(f"\n  🎉 成功！提取到 {total} 个测试点:")
            for i, item in enumerate(items[:5], 1):
                print(f"     {i}. [{item.get('module', '?')}] {item.get('point', '?')[:60]}")
        else:
            print(f"\n  ⚠️  返回空列表！开始深度排查...")

            # 3. 直接测试内部函数
            print("\n[3] 直接测试 extract_test_points_from_content 函数...")
            sys.path.insert(0, '.')

            from app.db.database import PrimarySessionLocal
            from app.models.project import ProjectFile
            from app.services.file_content_extractor import FileContentExtractor
            from app.services.ai_analysis_service import extract_test_points_from_content

            db = PrimarySessionLocal()
            try:
                # 获取文件
                file_record = db.query(ProjectFile).filter(ProjectFile.id == 1).first()
                if not file_record:
                    print("  ❌ 文件不存在")
                    return

                print(f"  文件: {file_record.file_name}")

                # 提取内容
                extractor = FileContentExtractor(db)
                extract_result = await extractor.extract_file_content(file_record, force_refresh=False)

                if not extract_result.get("success"):
                    print(f"  ❌ 文件内容提取失败: {extract_result.get('error')}")
                    return

                content = extract_result.get("content", "")
                print(f"  内容长度: {len(content)} 字符")

                if not content:
                    print("  ❌ 内容为空！这就是原因")
                    return

                # 直接调用AI函数
                print(f"\n  调用 AI 分析...")
                test_points = await extract_test_points_from_content(
                    content=content,
                    project_id=file_record.project_id,
                    user_id=1
                )

                print(f"\n  ✅ 直接调用结果: {len(test_points)} 个测试点")

                if test_points:
                    for i, tp in enumerate(test_points[:3], 1):
                        print(f"     {i}. {tp.get('point', '?')[:60]}")
                else:
                    print("\n  ❌ 直接调用也返回空！问题在AI函数内部")

                    # 进一步测试：直接调用ai_client
                    print("\n[4] 直接调用 ai_client.analyze_requirements_stream...")
                    from app.utils.ai_client import ai_client

                    chunk_count = 0
                    got_data = False

                    async for chunk in ai_client.analyze_requirements_stream(content):
                        chunk_count += 1
                        if "data" in chunk:
                            got_data = True
                            data_list = chunk.get("data", [])
                            print(f"  📦 收到data chunk! 长度: {len(data_list)}")
                            if data_list:
                                print(f"  ✅ AI确实返回了 {len(data_list)} 个测试点")

                    print(f"\n  总chunk数: {chunk_count}")
                    print(f"  是否收到data: {'是' if got_data else '否'}")

                    if not got_data:
                        print("\n  🔍 问题定位:")
                        print("     ai_client 没有yield包含'data'的chunk")
                        print("     可能原因:")
                        print("     ① AI响应解析失败（JSON格式错误）")
                        print("     ② AI返回了非JSON内容")
                        print("     ③ 流式响应未正常结束")

            finally:
                db.close()

    except requests.exceptions.Timeout:
        print("\n  ❌ 请求超时！")
    except Exception as e:
        print(f"\n  ❌ 异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_extract_pipeline())
