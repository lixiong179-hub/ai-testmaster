"""test_case_crud_batch.py batch-create 端点 async 测试补充。

test_test_case_crud_api.py 已覆盖 batch-delete/batch-restore（端测双迁）。
本文件覆盖 batch-create 端点的权限拦截、正常创建、未授权项目场景。
"""
from datetime import datetime


class TestCaseCrudBatchCreateAsync:
    """batch-create 端点 async 测试。"""

    async def test_batch_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-case/batch-create",
            json={
                "cases": [
                    {
                        "project_id": 1,
                        "title": "未认证用例",
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                    }
                ]
            },
        )
        assert resp.status_code in (401, 403, 404)

    async def test_batch_create_empty_cases_rejected(self, async_auth_client):
        """空列表应在 schema 校验阶段 422 拒绝。"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-create",
            json={"cases": []},
        )
        assert resp.status_code in (400, 422)

    async def test_batch_create_unauthorized_project(
        self, async_auth_client
    ):
        """未授权项目应在 endpoint 内返回 200 + fail_count 错误响应。"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-create",
            json={
                "cases": [
                    {
                        "project_id": 99999,
                        "title": "未授权用例",
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                    }
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["success_count"] == 0
        assert data["fail_count"] == 1

    async def test_batch_create_success(
        self, async_auth_client, async_test_project
    ):
        case_no = f"CASE-ASYNC-BATCH-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-create",
            json={
                "cases": [
                    {
                        "project_id": async_test_project.id,
                        "case_no": case_no,
                        "title": "异步批量创建用例",
                        "module": "batch_module",
                        "precondition": "无",
                        "steps": [{"step": 1, "action": "打开页面", "expected_result": "显示页面"}],
                        "expected_result": "成功",
                        "priority": 2,
                        "case_type": "manual",
                    },
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["success_count"] == 1
        assert data["fail_count"] == 0
        assert len(data["created_ids"]) == 1
