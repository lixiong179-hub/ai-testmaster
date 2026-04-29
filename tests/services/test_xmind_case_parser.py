"""XMind 场景树解析器单元测试。"""
import zipfile

from app.services.xmind_case_parser import XmindCaseParser


NS = "urn:xmind:xmap:xmlns:content:2.0"


def _create_xmind_file(path: str, content_xml: str) -> str:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        zf.writestr("meta.xml", '<?xml version="1.0" encoding="UTF-8"?>')
    return path


def _build_content_xml(topics_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-content xmlns="{NS}" version="2.0">
<sheet id="test-sheet">
<topic id="root" structure-class="org.xmind.ui.logic.right">
<title>听写任务</title>
<children><topics type="attached">
{topics_xml}
</topics></children>
</topic>
</sheet>
</xmap-content>"""


def _build_topic(title: str, topic_id: str, children_xml: str = "") -> str:
    children_part = (
        f"<children><topics type='attached'>{children_xml}</topics></children>"
        if children_xml
        else ""
    )
    return f"""<topic id="{topic_id}">
<title>{title}</title>
{children_part}
</topic>"""


def test_parse_scenario_tree_to_case(tmp_path) -> None:
    leaf = _build_topic("界面显示最近的听写记录", "leaf")
    has_record = _build_topic("有记录", "has-record", children_xml=leaf)
    click_record = _build_topic("点击听写记录", "click-record", children_xml=has_record)
    has_content = _build_topic("有教材内容", "has-content", children_xml=click_record)
    module = _build_topic("字词听写", "module", children_xml=has_content)
    xmind_file = _create_xmind_file(
        str(tmp_path / "scenario.xmind"),
        _build_content_xml(module),
    )

    parser = XmindCaseParser()
    result = parser.parse(xmind_file)

    assert len(result) == 1
    assert result[0]["module"] == "字词听写"
    # function 是AI中间产物，不存库，仅作提示词上下文
    assert "function" in result[0]  # 瞬态字段，从XMind二级节点推断
    assert result[0]["title"] == "点击听写记录，界面显示最近的听写记录"
    assert "有教材内容" in result[0]["precondition"]
    assert "有记录" in result[0]["precondition"]
    assert result[0]["steps"][0]["action"] == "点击听写记录"
    assert result[0]["expected_result"] == "界面显示最近的听写记录"
    assert result[0]["point"] == result[0]["title"]
    assert result[0]["source_depth"] == 4


def test_parse_multiple_actions_to_multi_step_case(tmp_path) -> None:
    leaf = _build_topic("跳转到结果页", "leaf")
    submit = _build_topic("点击提交", "submit", children_xml=leaf)
    write = _build_topic("开始屏幕听写", "write", children_xml=submit)
    selected = _build_topic("已选汉字", "selected", children_xml=write)
    module = _build_topic("字词听写", "module", children_xml=selected)
    xmind_file = _create_xmind_file(
        str(tmp_path / "multi_step.xmind"),
        _build_content_xml(module),
    )

    parser = XmindCaseParser()
    result = parser.parse(xmind_file)

    assert len(result) == 1
    assert [step["action"] for step in result[0]["steps"]] == ["开始屏幕听写", "点击提交"]
    assert result[0]["steps"][-1]["expected_result"] == "跳转到结果页"


def test_do_not_dedupe_cases_with_different_steps(tmp_path) -> None:
    leaf1 = _build_topic("跳转到结果页", "leaf1")
    action1 = _build_topic("点击提交", "action1", children_xml=leaf1)
    scene1 = _build_topic("已选汉字", "scene1", children_xml=action1)

    leaf2 = _build_topic("跳转到结果页", "leaf2")
    action2_leaf = _build_topic("点击提交", "action2-leaf", children_xml=leaf2)
    action2 = _build_topic("开始屏幕听写", "action2", children_xml=action2_leaf)
    scene2 = _build_topic("已选汉字", "scene2", children_xml=action2)

    module = _build_topic("字词听写", "module", children_xml=scene1 + scene2)
    xmind_file = _create_xmind_file(
        str(tmp_path / "dedupe_case.xmind"),
        _build_content_xml(module),
    )

    parser = XmindCaseParser()
    result = parser.parse(xmind_file)

    assert len(result) == 2
    action_signatures = {tuple(step["action"] for step in item["steps"]) for item in result}
    assert ("点击提交",) in action_signatures
    assert ("开始屏幕听写", "点击提交") in action_signatures
