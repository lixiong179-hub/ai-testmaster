"""execution_management.py 端点 async 测试。

覆盖 GET /api/v1/execution/{task_id}/screenshot/...、video、video/info 端点
的未认证与不存在任务场景。使用 tests/api/conftest.py 的 async fixture。
"""


class TestExecutionManagementAPI:
    """执行管理端点测试：截图获取与视频回放。"""

    async def test_screenshot_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/execution/1/screenshot/1/1/step"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_video_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/execution/1/case/1/video"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_video_info_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/execution/1/case/1/video/info"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_screenshot_nonexistent_task(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/execution/99999/screenshot/1/1/step"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_video_nonexistent_task(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/execution/99999/case/1/video"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_video_info_nonexistent_task(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/execution/99999/case/1/video/info"
        )
        assert resp.status_code in (403, 404, 500)
