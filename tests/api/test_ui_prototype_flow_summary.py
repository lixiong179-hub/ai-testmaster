from app.api.v1.endpoints.ui_prototype.project_endpoints import _build_flow_summary


def test_build_flow_summary_from_merged_flow() -> None:
    summary = _build_flow_summary(
        {
            "entry_screen": "登录页",
            "end_screens": ["首页"],
            "page_flows": [
                {
                    "from_screen": "登录页",
                    "to_screen": "首页",
                    "trigger_action": "点击登录",
                    "condition": "账号密码正确",
                },
                {
                    "from_screen": "登录页",
                    "to_screen": "错误提示",
                    "trigger_action": "点击登录",
                },
            ],
            "key_user_paths": [{"path_name": "主路径", "steps": ["登录页", "首页"]}],
            "warnings": ["错误提示页需要确认"],
        }
    )

    assert summary["has_flow"] is True
    assert summary["node_count"] == 3
    assert summary["edge_count"] == 2
    assert summary["entry_screen"] == "登录页"
    assert summary["end_screens"] == ["首页"]
    assert summary["branch_count"] == 1
    assert summary["exception_count"] == 1
    assert summary["key_path_count"] == 1


def test_build_flow_summary_handles_empty_flow() -> None:
    summary = _build_flow_summary(None)

    assert summary["has_flow"] is False
    assert summary["node_count"] == 0
    assert summary["edge_count"] == 0
