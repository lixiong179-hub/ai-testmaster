import pytest
from app.utils.unified_vision_model._types import (
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS,
)


class TestVisionModelType:
    def test_all_values(self):
        assert VisionModelType.KIMI.value == "kimi"
        assert VisionModelType.ZHIPU.value == "zhipu"
        assert VisionModelType.BAIDU.value == "baidu"
        assert VisionModelType.QWEN.value == "qwen"
        assert VisionModelType.DOUBAO.value == "doubao"
        assert VisionModelType.MIMO.value == "mimo"

    def test_from_string(self):
        assert VisionModelType("kimi") == VisionModelType.KIMI
        assert VisionModelType("mimo") == VisionModelType.MIMO

    def test_invalid_string(self):
        with pytest.raises(ValueError):
            VisionModelType("nonexistent")


class TestElementInfo:
    def test_normal(self):
        elem = ElementInfo(
            type="button",
            text="登录",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.95,
        )
        assert elem.type == "button"
        assert elem.text == "登录"
        assert elem.confidence == 0.95

    def test_boundary_confidence(self):
        elem = ElementInfo(
            type="input", text="", x=0, y=0, width=1, height=1, confidence=0.0,
        )
        assert elem.confidence == 0.0


class TestModelProviderConfigs:
    def test_all_types_have_config(self):
        for model_type in VisionModelType:
            assert model_type in MODEL_PROVIDER_CONFIGS

    def test_config_structure(self):
        for model_type, config in MODEL_PROVIDER_CONFIGS.items():
            assert isinstance(config, ModelProviderConfig)
            assert config.model_type == model_type
            assert config.api_key_env
            assert config.base_url_env
            assert config.model_name_env
            assert config.default_base_url
            assert config.default_model_name

    def test_kimi_config(self):
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.KIMI]
        assert "moonshot" in config.default_base_url

    def test_mimo_config(self):
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.MIMO]
        assert "mimo" in config.default_model_name


class TestCreateVisionModel:
    def test_create_default(self):
        from app.utils.unified_vision_model._model import create_vision_model
        model = create_vision_model("mimo")
        assert model is not None

    def test_create_with_invalid_type(self):
        from app.utils.unified_vision_model._model import create_vision_model
        model = create_vision_model("nonexistent_type")
        assert model is not None

    def test_create_with_none(self):
        from app.utils.unified_vision_model._model import create_vision_model
        model = create_vision_model(None)
        assert model is not None
