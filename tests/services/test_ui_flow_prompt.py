from app.services.prompt_builder.constants import MULTI_IMAGE_FLOW_PROMPT


def test_multi_image_flow_prompt_json_example_is_format_safe() -> None:
    prompt = MULTI_IMAGE_FLOW_PROMPT.format(
        count=2,
        image_descriptions="【屏幕1】资源列表\n\n【屏幕2】UI原型详情",
    )

    assert '"entry_screen"' in prompt
    assert '"page_flows"' in prompt
    assert "【屏幕1】资源列表" in prompt
