import time
import pytest
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimitMiddleware


class TestRateLimitInit:
    def test_init_stores_params(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=100, time_window=60)
        assert middleware.max_requests == 100
        assert middleware.time_window == 60

    def test_init_custom_params(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=50, time_window=30)
        assert middleware.max_requests == 50
        assert middleware.time_window == 30

    def test_init_has_requests_dict(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=60)
        assert hasattr(middleware, "requests")
        assert isinstance(middleware.requests, dict)

    def test_init_redis_flag(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=60)
        assert isinstance(middleware._use_redis, bool)


class TestCleanupOldRequests:
    def test_cleanup_removes_expired(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=1)
        ip = "127.0.0.1"
        old_time = time.time() - 2
        middleware.requests[ip].append(old_time)
        current_time = time.time()
        middleware._cleanup_old_requests(ip, current_time)
        assert ip not in middleware.requests

    def test_cleanup_keeps_valid(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=60)
        ip = "127.0.0.1"
        current_time = time.time()
        middleware.requests[ip].append(current_time)
        middleware._cleanup_old_requests(ip, current_time)
        assert ip in middleware.requests
        assert len(middleware.requests[ip]) == 1

    def test_cleanup_empty_deque_removes_key(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=1)
        ip = "192.168.1.1"
        old_time = time.time() - 5
        middleware.requests[ip].append(old_time)
        middleware._cleanup_old_requests(ip, time.time())
        assert ip not in middleware.requests

    def test_cleanup_partial_expiry(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=5)
        ip = "10.0.0.1"
        current_time = time.time()
        middleware.requests[ip].append(current_time - 10)
        middleware.requests[ip].append(current_time - 1)
        middleware._cleanup_old_requests(ip, current_time)
        assert len(middleware.requests[ip]) == 1

    def test_cleanup_nonexistent_ip(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=60)
        middleware._cleanup_old_requests("nonexistent_ip", time.time())

    def test_cleanup_multiple_expired(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=5)
        ip = "172.16.0.1"
        current_time = time.time()
        middleware.requests[ip].append(current_time - 10)
        middleware.requests[ip].append(current_time - 8)
        middleware.requests[ip].append(current_time - 1)
        middleware._cleanup_old_requests(ip, current_time)
        assert len(middleware.requests[ip]) == 1


class TestDispatchMemory:
    @pytest.mark.asyncio
    async def test_dispatch_memory_under_limit(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=5, time_window=60)
        middleware._use_redis = False

        async def mock_call_next(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": True})

        from starlette.testclient import TestClient
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        current_time = time.time()
        response = await middleware._dispatch_memory("127.0.0.1", current_time, request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_memory_over_limit(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=2, time_window=60)
        middleware._use_redis = False

        async def mock_call_next(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": True})

        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        current_time = time.time()
        middleware.requests["127.0.0.1"].append(current_time)
        middleware.requests["127.0.0.1"].append(current_time)
        with pytest.raises(HTTPException) as exc_info:
            await middleware._dispatch_memory("127.0.0.1", current_time, request, mock_call_next)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_dispatch_memory_records_timestamp(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=5, time_window=60)
        middleware._use_redis = False

        async def mock_call_next(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": True})

        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        current_time = time.time()
        await middleware._dispatch_memory("127.0.0.1", current_time, request, mock_call_next)
        assert len(middleware.requests["127.0.0.1"]) == 1


class TestDispatchRedisFallback:
    @pytest.mark.asyncio
    async def test_dispatch_redis_fallback_on_error(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=5, time_window=60)
        middleware._use_redis = True
        middleware._redis_client = None

        async def mock_call_next(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": True})

        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        current_time = time.time()
        response = await middleware._dispatch_redis("127.0.0.1", current_time, request, mock_call_next)
        assert response.status_code == 200


class TestRateLimitEdgeCases:
    def test_deque_maxlen(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=5, time_window=60)
        ip = "127.0.0.1"
        assert middleware.requests[ip].maxlen == 5

    def test_multiple_ips_independent(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=2, time_window=60)
        ip1 = "1.1.1.1"
        ip2 = "2.2.2.2"
        current_time = time.time()
        middleware.requests[ip1].append(current_time)
        middleware.requests[ip1].append(current_time)
        assert len(middleware.requests[ip1]) == 2
        assert len(middleware.requests[ip2]) == 0

    @pytest.mark.asyncio
    async def test_dispatch_unknown_client_ip(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=5, time_window=60)
        middleware._use_redis = False

        async def mock_call_next(request):
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": True})

        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "client": None,
        }
        request = Request(scope)
        current_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        response = await middleware._dispatch_memory(client_ip, current_time, request, mock_call_next)
        assert response.status_code == 200

    def test_cleanup_boundary_time(self):
        middleware = RateLimitMiddleware(FastAPI(), max_requests=10, time_window=5)
        ip = "10.0.0.2"
        current_time = time.time()
        boundary_time = current_time - 5
        middleware.requests[ip].append(boundary_time)
        middleware._cleanup_old_requests(ip, current_time)
        assert len(middleware.requests[ip]) == 1
