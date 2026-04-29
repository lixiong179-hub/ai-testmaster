# 多模态视觉模型使用指南

本项目支持多种国内多模态视觉大模型，通过**统一适配器**实现动态切换。

## 支持的模型

| 模型 | 类型 | 厂商 | 特点 |
|------|------|------|------|
| Kimi | `kimi` | Moonshot | 128K上下文，视觉理解能力强 |
| 智谱GLM-4V | `zhipu` | 智谱AI | 中文理解优秀 |
| 通义千问VL | `qwen` | 阿里云 | 多语言支持好 |
| 文心一言 | `baidu` | 百度 | 中文场景优化 |
| 豆包 | `doubao` | 字节跳动 | OpenAI兼容格式 |

## 设计思路

**为什么使用统一适配器而不是多个适配器类？**

1. **国内模型API高度统一**：Kimi、智谱、豆包等都采用OpenAI兼容格式
2. **减少代码冗余**：避免80%的重复代码（base64编码、重试逻辑、错误处理等）
3. **易于维护**：修改通用逻辑只需改一处
4. **动态配置**：通过配置即可切换模型，无需创建新类

只有通义千问和文心一言有轻微差异，通过条件判断处理即可。

## 配置方法

### 1. 环境变量配置

在 `.env` 文件中配置：

```env
# 设置默认模型
DEFAULT_VISION_MODEL=kimi

# 配置各模型的API Key
KIMI_API_KEY=your_kimi_api_key
ZHIPU_API_KEY=your_zhipu_api_key
QWEN_API_KEY=your_qwen_api_key
BAIDU_API_KEY=your_baidu_api_key
DOUBAO_API_KEY=your_doubao_api_key
```

### 2. 代码中使用

#### 使用默认模型

```python
from app.utils.unified_vision_model import get_default_vision_model

# 获取默认模型
model = get_default_vision_model()

# 识别元素
elements = model.recognize_bytes(screenshot, "登录按钮")

# 描述截图
description = model.describe_screenshot(screenshot)

# 验证操作结果
success, reason = model.verify_action_result(
    before_screenshot, 
    after_screenshot,
    "点击登录按钮",
    "跳转到首页"
)
```

#### 使用指定模型（超级简单）

```python
from app.utils.unified_vision_model import create_vision_model

# 一行代码切换模型
model = create_vision_model("zhipu")  # 或 "kimi", "qwen", "baidu", "doubao"

# 使用模型
elements = model.recognize_bytes(screenshot, "提交按钮")
```

#### 自定义配置

```python
from app.utils.unified_vision_model import UnifiedVisionModel, VisionModelType

# 完全自定义配置
model = UnifiedVisionModel(
    model_type=VisionModelType.KIMI,
    api_key="your_api_key",
    base_url="https://custom.api.endpoint/v1",
    model_name="custom-model",
    max_retries=5,
    timeout=120
)
```

## API接口

### 元素识别

```python
elements = model.recognize_bytes(
    screenshot: bytes,      # 截图字节数据
    description: str,       # 元素描述
    min_confidence: float = 0.9  # 最小置信度
)

# 返回 ElementInfo 列表
for elem in elements:
    print(f"类型: {elem.type}, 位置: ({elem.x}, {elem.y}), 置信度: {elem.confidence}")
```

### 描述截图

```python
description = model.describe_screenshot(screenshot: bytes)
print(description)
```

### 验证操作结果

```python
success, reason = model.verify_action_result(
    before_screenshot: bytes,   # 操作前截图
    after_screenshot: bytes,    # 操作后截图
    action_description: str,    # 操作描述
    expected_result: str        # 预期结果
)

if success:
    print(f"验证通过: {reason}")
else:
    print(f"验证失败: {reason}")
```

## 添加新模型

如需添加新的视觉模型支持，只需修改配置：

```python
from app.utils.unified_vision_model import MODEL_PROVIDER_CONFIGS, ModelProviderConfig, VisionModelType

# 添加新模型配置
MODEL_PROVIDER_CONFIGS[VisionModelType.NEWMODEL] = ModelProviderConfig(
    model_type=VisionModelType.NEWMODEL,
    api_key_env="NEWMODEL_API_KEY",
    base_url_env="NEWMODEL_BASE_URL",
    model_name_env="NEWMODEL_MODEL",
    default_base_url="https://api.newmodel.com/v1",
    default_model_name="newmodel-vision"
)
```

如果新模型有特殊格式，可以在 `UnifiedVisionModel` 中添加条件处理。

## 注意事项

1. **API Key安全**: 不要将API Key硬编码在代码中，使用环境变量
2. **错误处理**: 模型调用可能失败，建议添加try-except处理
3. **成本控制**: 视觉模型调用费用较高，注意控制调用频率
4. **响应时间**: 视觉模型响应较慢，建议设置合理的超时时间
