"""拆分验证脚本 - 验证 test_case_ai.py 拆分后功能完整性"""
import sys


def test_imports():
    """验证所有模块导入正常"""
    # 1. 子模块直接导入
    from app.api.v1.endpoints.test_case_ai_helpers import (
        _prepare_test_point,
        _build_ui_specs_text,
        _build_graph_prompt_data,
        _build_linear_prompt_data,
        _format_case_response,
    )
    print("[PASS] test_case_ai_helpers imports OK")

    from app.api.v1.endpoints.test_case_ai_schemas import (
        AIGenerateRequest,
        AIGenerateEnhancedRequest,
        GenerateContextRequest,
        SingleGenerateRequest,
        BatchGenerateRequest,
        MAX_FLOW_NODES,
        MAX_FLOW_EDGES,
    )
    print("[PASS] test_case_ai_schemas imports OK")

    from app.api.v1.endpoints.test_case_ai_generate import router as generate_router
    print("[PASS] test_case_ai_generate imports OK")

    from app.api.v1.endpoints.test_case_ai_preview import (
        router as preview_router,
        PreviewGraphPromptRequest,
        PreviewGraphPromptResponse,
    )
    print("[PASS] test_case_ai_preview imports OK")

    # 2. 主入口向后兼容导入
    from app.api.v1.endpoints.test_case_ai import (
        router,
        AIGenerateRequest,
        AIGenerateEnhancedRequest,
        GenerateContextRequest,
        SingleGenerateRequest,
        BatchGenerateRequest,
        MAX_FLOW_NODES,
        MAX_FLOW_EDGES,
        _build_graph_prompt_data,
        _build_linear_prompt_data,
        _format_case_response,
        PreviewGraphPromptRequest,
        PreviewGraphPromptResponse,
    )
    print("[PASS] test_case_ai backward-compatible imports OK")

    # 3. 流式模块导入（依赖 test_case_ai 的向后兼容导出）
    from app.api.v1.endpoints.test_case_ai_stream import router as stream_router
    print("[PASS] test_case_ai_stream imports OK")

    return router


def test_routes(router):
    """验证所有路由路径和方法完整"""
    routes = {}
    for r in router.routes:
        path = r.path
        methods = r.methods
        if path in routes:
            routes[path] = routes[path] | methods
        else:
            routes[path] = methods

    expected = {
        "/ai-generate": {"POST"},
        "/ai-enhanced-generate": {"POST"},
        "/generate-context": {"POST"},
        "/generate-single": {"POST"},
        "/ai-batch-generate": {"POST"},
        "/{case_id}/precondition-steps": {"GET", "PUT"},
        "/{case_id}/parse-precondition": {"POST"},
        "/preview-graph-prompt": {"POST"},
    }

    all_ok = True
    for path, methods in expected.items():
        if path not in routes:
            print(f"[FAIL] MISSING route: {path}")
            all_ok = False
        elif not methods.issubset(routes[path]):
            print(f"[FAIL] MISSING methods for {path}: expected {methods}, got {routes[path]}")
            all_ok = False
        else:
            print(f"[PASS] Route {path} {methods}")

    return all_ok


def test_schemas():
    """验证Pydantic模型基本功能"""
    from app.api.v1.endpoints.test_case_ai_schemas import (
        AIGenerateRequest,
        AIGenerateEnhancedRequest,
        GenerateContextRequest,
        SingleGenerateRequest,
        BatchGenerateRequest,
    )

    # AIGenerateRequest
    req = AIGenerateRequest(project_id=1, description="test description that is long enough")
    assert req.project_id == 1
    print("[PASS] AIGenerateRequest basic validation")

    # AIGenerateEnhancedRequest
    req2 = AIGenerateEnhancedRequest(project_id=1, description="test desc for enhanced")
    assert req2.mode == "linear"
    print("[PASS] AIGenerateEnhancedRequest basic validation")

    # GenerateContextRequest
    req3 = GenerateContextRequest(project_id=1)
    assert req3.project_id == 1
    print("[PASS] GenerateContextRequest basic validation")

    # SingleGenerateRequest
    req4 = SingleGenerateRequest(project_id=1, test_point_id=1)
    assert req4.test_point_id == 1
    print("[PASS] SingleGenerateRequest basic validation")

    # BatchGenerateRequest
    req5 = BatchGenerateRequest(project_id=1)
    assert req5.project_id == 1
    print("[PASS] BatchGenerateRequest basic validation")

    return True


def test_helpers():
    """验证辅助函数基本功能"""
    from app.api.v1.endpoints.test_case_ai_helpers import (
        _prepare_test_point,
        _format_case_response,
    )

    # _prepare_test_point
    ctx = {"test_point": {"module": "m1", "point": "p1"}}
    tp = _prepare_test_point(ctx, "desc", 2)
    assert tp["module"] == "m1"
    print("[PASS] _prepare_test_point with existing test_point")

    ctx2 = {"module": "m2", "point": "p2"}
    tp2 = _prepare_test_point(ctx2, "desc", 3)
    assert tp2["module"] == "m2"
    assert tp2["priority"] == 3
    print("[PASS] _prepare_test_point with fallback construction")

    # _format_case_response
    generated = {
        "title": "test case",
        "priority": "high",
        "steps": [{"action": "step1", "expected_result": "result1"}],
    }
    resp = _format_case_response(generated, 1, "desc", 2, "manual")
    assert resp["project_id"] == 1
    assert resp["title"] == "test case"
    print("[PASS] _format_case_response basic validation")

    return True


def test_parent_router():
    """验证父模块 test_case.py 路由注册"""
    from app.api.v1.endpoints.test_case import router as parent_router

    ai_paths = set()
    for r in parent_router.routes:
        if hasattr(r, "path") and any(
            kw in r.path.lower()
            for kw in ("ai", "generate", "preview", "precondition")
        ):
            ai_paths.add(r.path)

    expected_paths = {
        "/testCase/ai-generate",
        "/testCase/ai-enhanced-generate",
        "/testCase/generate-context",
        "/testCase/generate-single",
        "/testCase/ai-batch-generate",
        "/testCase/{case_id}/precondition-steps",
        "/testCase/{case_id}/parse-precondition",
        "/testCase/preview-graph-prompt",
        "/testCase/ai-enhanced-generate/stream",
        "/testCase/batch-generate/stream",
    }

    missing = expected_paths - ai_paths
    if missing:
        print(f"[FAIL] Missing paths in parent router: {missing}")
        return False
    print(f"[PASS] Parent router has all {len(expected_paths)} AI-related paths")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Split verification for test_case_ai.py")
    print("=" * 60)

    try:
        router = test_imports()
        print()
        routes_ok = test_routes(router)
        print()
        schemas_ok = test_schemas()
        print()
        helpers_ok = test_helpers()
        print()
        parent_ok = test_parent_router()
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    if all([routes_ok, schemas_ok, helpers_ok, parent_ok]):
        print("ALL VERIFICATIONS PASSED")
        sys.exit(0)
    else:
        print("SOME VERIFICATIONS FAILED")
        sys.exit(1)
