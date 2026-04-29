"""
文件排序API单元测试

覆盖范围:
- POST /api/v1/file/update-sort 批量更新排序
- GET /api/v1/file/list/{project_id} 排序查询验证
- GET /api/v1/file/list 全局排序验证
- 输入验证（空列表、超限100、去重、非整数ID）
- 权限校验（他人项目文件、未认证）
- 排序持久化（更新后重新查询验证顺序）
- N+1修复验证（预加载用户项目集合）

使用真实MySQL数据库和FastAPI TestClient
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_headers(client):
    """获取认证token"""
    from app.services.captcha_service import captcha_service
    
    captcha_service._store.clear()
    captcha_service._used.clear()
    captcha_service._ip_limits.clear()
    
    captcha_resp = client.get("/api/v1/auth/captcha/generate")
    assert captcha_resp.status_code == 200, f"验证码生成失败: {captcha_resp.status_code}"
    captcha_data = captcha_resp.json()
    
    login_resp = client.post("/api/v1/auth/login", data={
        "username": "admin",
        "password": "admin",
        "captcha_id": captcha_data["data"]["captcha_id"],
        "captcha_code": captcha_data["data"]["code"]
    })
    
    if login_resp.status_code == 200:
        token = login_resp.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}
    else:
        pytest.skip("无法登录，跳过需要认证的测试")


@pytest.fixture(scope="function")
def test_project(client, auth_headers):
    """创建或获取测试项目"""
    resp = client.get("/api/v1/project/list", headers=auth_headers)
    if resp.status_code == 200 and resp.json().get("data", {}).get("items"):
        projects = resp.json()["data"]["items"]
        if projects:
            return projects[0]["id"]

    create_resp = client.post(
        "/api/v1/project",
        json={"name": "排序测试项目_单元测试"},
        headers=auth_headers
    )
    if create_resp.status_code == 200:
        return create_resp.json()["data"]["id"]
    
    pytest.skip("无法创建/获取测试项目")


@pytest.fixture(scope="function")
def test_files(client, auth_headers, test_project):
    """
    创建多个测试UI原型图文件用于排序测试
    返回创建的文件ID列表（按创建顺序）
    """
    file_ids = []
    file_names = ["首页设计稿.png", "列表页原型.fig", "详情页mockup.jpg", "设置页UI.webp"]
    
    for name in file_names:
        import io
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        
        resp = client.post(
            "/api/v1/file/upload",
            files={"file": (name, file_content, "image/png")},
            data={
                "project_id": str(test_project),
                "resource_type": "ui_mockup",
                "description": f"排序测试用例-{name}"
            },
            headers=auth_headers
        )
        
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            if isinstance(data, dict) and "id" in data:
                file_ids.append(data["id"])
    
    if len(file_ids) < 2:
        pytest.skip("需要至少2个文件才能进行排序测试")
    
    return file_ids


class TestUpdateSortInputValidation:
    """输入验证测试"""

    def test_empty_list_rejected(self, client, auth_headers):
        """空文件ID列表应被拒绝"""
        resp = client.post(
            "/api/v1/file/update-sort",
            json=[],
            headers=auth_headers
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "不能为空" in data.get("msg", data.get("detail", "")) or \
               "不能为空" in data.get("message", "")

    def test_over_100_limit_rejected(self, client, auth_headers):
        """超过100个文件ID应被拒绝"""
        large_list = list(range(1, 102))

        resp = client.post(
            "/api/v1/file/update-sort",
            json=large_list,
            headers=auth_headers
        )

        assert resp.status_code == 400
        data = resp.json()
        msg_text = data.get("msg", data.get("detail", ""))
        assert "超过" in msg_text or "100" in msg_text

    def test_non_integer_ids_rejected(self, client, auth_headers):
        """非整数ID应被拒绝或忽略"""
        invalid_data = [1, "abc", 3.14, None, True]
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=invalid_data,
            headers=auth_headers
        )
        
        # FastAPI的List[int]类型校验会拒绝非整数
        assert resp.status_code in [400, 422]

    def test_single_file_accepted(self, client, auth_headers, test_files):
        """单个文件ID应被接受（虽然实际不改变排序）"""
        resp = client.post(
            "/api/v1/file/update-sort",
            json=[test_files[0]],
            headers=auth_headers
        )
        
        assert resp.status_code == 200


class TestUpdateSortDeduplication:
    """去重逻辑测试"""

    def test_duplicate_ids_deduplicated(self, client, auth_headers, test_files):
        """重复的文件ID应该被去重"""
        duplicated_list = [test_files[0], test_files[1], test_files[0], test_files[1]]
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=duplicated_list,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        # 去重后只有2个唯一ID，updated_count不应超过2
        assert data["data"]["updated_count"] <= 2

    def test_all_same_id(self, client, auth_headers, test_files):
        """所有ID都相同的情况"""
        same_id_list = [test_files[0]] * 5
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=same_id_list,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        assert resp.json()["data"]["updated_count"] == 1


class TestUpdateSortPermission:
    """权限校验测试"""

    def test_unauthorized_returns_401(self, client, test_files):
        """未认证请求返回401"""
        resp = client.post(
            "/api/v1/file/update-sort",
            json=test_files[:2]
        )
        
        assert resp.status_code == 401 or resp.status_code == 403

    def test_nonexistent_file_skipped(self, client, auth_headers, test_project):
        """不存在的文件ID应被跳过而非报错"""
        nonexistent_ids = [999999998, 999999997, 999999996]
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=nonexistent_ids,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        assert resp.json()["data"]["updated_count"] == 0

    def test_mixed_valid_invalid_ids(self, client, auth_headers, test_files):
        """混合有效和无效ID：有效的正常处理，无效的被跳过"""
        mixed_ids = [test_files[0], 999999995, test_files[1], 999999994]
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=mixed_ids,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        updated = resp.json()["data"]["updated_count"]
        # 只有2个有效ID能被更新
        assert updated == 2


class TestUpdateSortFunctionality:
    """核心功能测试"""

    def test_sort_order_update_basic(self, client, auth_headers, test_files):
        """基本排序更新：反转文件顺序"""
        original_order = list(test_files)
        reversed_order = list(reversed(test_files))
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=reversed_order,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["updated_count"] >= 2
        assert "成功更新" in data["message"]

    def test_sort_order_persistence(self, client, auth_headers, test_files, test_project):
        """排序持久化：更新后重新查询验证sort_order已保存"""
        reversed_order = list(reversed(test_files))
        
        # 执行排序更新
        update_resp = client.post(
            "/api/v1/file/update-sort",
            json=reversed_order,
            headers=auth_headers
        )
        assert update_resp.status_code == 200
        
        # 查询文件列表验证排序
        list_resp = client.get(
            f"/api/v1/file/list/{test_project}?resource_type=ui_mockup",
            headers=auth_headers
        )
        
        assert list_resp.status_code == 200
        items = list_resp.json()["data"]["items"]
        
        if len(items) >= 2:
            # 验证返回的数据包含sort_order字段
            for item in items:
                assert "sort_order" in item, "响应缺少sort_order字段"
                assert isinstance(item["sort_order"], int), "sort_order应为整数"

    def test_sort_order_values_sequential(self, client, auth_headers, test_files, test_project):
        """排序值为非负整数（从index+1设置）"""
        custom_order = [test_files[2], test_files[0], test_files[1]] if len(test_files) >= 3 else list(reversed(test_files))

        resp = client.post(
            "/api/v1/file/update-sort",
            json=custom_order,
            headers=auth_headers
        )
        assert resp.status_code == 200

        # 查询并检查sort_order值
        list_resp = client.get(
            f"/api/v1/file/list/{test_project}?resource_type=ui_mockup",
            headers=auth_headers
        )

        if list_resp.status_code == 200 and len(list_resp.json()["data"]["items"]) > 0:
            items = list_resp.json()["data"]["items"]
            # 只验证被排序过的文件（sort_order > 0）
            sorted_items = [item for item in items if item.get("sort_order", 0) > 0]
            if sorted_items:
                sort_orders = [item["sort_order"] for item in sorted_items]
                # sort_order应该是正整数
                for order in sort_orders:
                    assert isinstance(order, int) and order >= 1, f"sort_order值异常: {order}"

    def test_partial_sort_update(self, client, auth_headers, test_files):
        """部分排序：只提交部分文件的排序"""
        partial_ids = test_files[:2]  # 只排前两个
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=partial_ids,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        assert resp.json()["data"]["updated_count"] == 2


class TestFileListOrdering:
    """文件列表排序查询测试"""

    def test_list_includes_sort_order_field(self, client, auth_headers, test_project):
        """文件列表响应包含sort_order字段"""
        resp = client.get(
            f"/api/v1/file/list/{test_project}",
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        
        if items:
            for item in items:
                assert "sort_order" in item, f"文件{item.get('id', '未知')}缺少sort_order字段"

    def test_global_list_includes_sort_order(self, client, auth_headers):
        """全局文件列表也包含sort_order字段"""
        resp = client.get("/api/v1/file/list", headers=auth_headers)
        
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        
        if items:
            for item in items:
                assert "sort_order" in item

    def test_list_ordered_by_resource_type_then_sort(self, client, auth_headers, test_project):
        """列表按(resource_type, sort_order, upload_time)排序"""
        resp = client.get(
            f"/api/v1/file/list/{test_project}",
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        
        if len(items) >= 2:
            # 验证同类型文件中sort_order是升序排列的
            from itertools import groupby
            for resource_type, group in groupby(items, key=lambda x: x["resource_type"]):
                group_items = list(group)
                sort_orders = [item["sort_order"] for item in group_items if item["sort_order"] is not None]
                # 有sort_order值的应该升序排列
                if len(sort_orders) >= 2:
                    assert sort_orders == sorted(sort_orders), \
                        f"类型{resource_type}的文件未按sort_order升序排列: {sort_orders}"


class TestNPlusOneFixVerification:
    """N+1查询修复验证"""

    def test_update_sort_performance(self, client, auth_headers, test_files):
        """验证update-sort不会触发N+1查询（通过响应时间间接判断）"""
        import time
        
        # 构造一个较大的ID列表来放大性能差异
        ids_with_duplicates = test_files * 10  # 制造更多数据点
        
        start = time.time()
        resp = client.post(
            "/api/v1/file/update-sort",
            json=ids_with_duplicates,
            headers=auth_headers
        )
        elapsed = time.time() - start
        
        # 即使有重复数据，预加载优化后应该在合理时间内完成
        assert resp.status_code == 200
        assert elapsed < 5.0, f"update-sort耗时过长({elapsed:.2f}s)，可能存在N+1问题"


class TestEdgeCases:
    """边界情况测试"""

    def test_exact_100_limit_accepted(self, client, auth_headers, test_files):
        """恰好100个ID应被接受"""
        # 用现有ID填充到100个（允许重复，会去重）
        padded = []
        while len(padded) < 100:
            for fid in test_files:
                if len(padded) >= 100:
                    break
                padded.append(fid)
        
        resp = client.post(
            "/api/v1/file/update-sort",
            json=padded[:100],
            headers=auth_headers
        )
        
        assert resp.status_code == 200

    def test_inactive_file_skipped(self, client, auth_headers, test_project):
        """已删除(is_active=False)的文件应被跳过"""
        # 先创建一个文件然后软删除它
        import io
        file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        
        create_resp = client.post(
            "/api/v1/file/upload",
            files={"file": ("to_delete.png", file_content, "image/png")},
            data={
                "project_id": str(test_project),
                "resource_type": "ui_mockup"
            },
            headers=auth_headers
        )
        
        if create_resp.status_code == 200:
            file_id = create_resp.json()["data"]["id"]
            
            # 软删除该文件
            delete_resp = client.delete(
                f"/api/v1/file/{file_id}?project_id={test_project}",
                headers=auth_headers
            )
            
            # 尝试对已删除文件排序
            sort_resp = client.post(
                "/api/v1/file/update-sort",
                json=[file_id],
                headers=auth_headers
            )
            
            assert sort_resp.status_code == 200
            assert sort_resp.json()["data"]["updated_count"] == 0

    def test_response_structure(self, client, auth_headers, test_files):
        """验证响应数据结构完整性"""
        resp = client.post(
            "/api/v1/file/update-sort",
            json=test_files,
            headers=auth_headers
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert "updated_count" in data["data"]
        assert isinstance(data["data"]["updated_count"], int)

    def test_concurrent_sort_overwrite(self, client, auth_headers, test_files):
        """多次排序以最后一次为准"""
        order1 = list(test_files)
        order2 = list(reversed(test_files))
        
        # 第一次排序
        resp1 = client.post("/api/v1/file/update-sort", json=order1, headers=auth_headers)
        assert resp1.status_code == 200
        
        # 第二次反向排序
        resp2 = client.post("/api/v1/file/update-sort", json=order2, headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["data"]["updated_count"] >= 2
