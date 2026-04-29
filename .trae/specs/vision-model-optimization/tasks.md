# Tasks

- [x] Task 1: 配置层改造 — 修改config.py新增配置项，修改AI自愈默认值
  - [x] SubTask 1.1: 在 `app/core/config.py` 中新增 `UI_PARSER_MODE: str = "text"` 配置项
  - [x] SubTask 1.2: 将 `AI_SELF_HEALING_ENABLED` 默认值从 `True` 改为 `False`
  - [x] SubTask 1.3: 将 `QWEN_MODEL` 默认值从 `qwen3-vl-flash` 改为 `qwen-vl-plus`

- [x] Task 2: UnifiedVisionModel新增纯文本调用方法
  - [x] SubTask 2.1: 在 `app/utils/unified_vision_model.py` 中新增 `analyze_text(prompt, system_prompt, temperature)` 方法
  - [x] SubTask 2.2: `analyze_text` 不传图片，仅构建纯文本messages发送给LLM
  - [x] SubTask 2.3: 复用已有的 `_make_request` 和重试逻辑

- [x] Task 3: OCR文本提取器实现
  - [x] SubTask 3.1: 新建 `app/utils/ocr_extractor.py`，封装PaddleOCR调用
  - [x] SubTask 3.2: 实现 `extract_text(image_bytes) -> str` 方法，返回提取的纯文本
  - [x] SubTask 3.3: 实现 `extract_text_with_position(image_bytes) -> List[Dict]` 方法，返回文字及大致位置
  - [x] SubTask 3.4: 处理PaddleOCR未安装时的降级逻辑，抛出明确异常

- [x] Task 4: UISpecParser双模式改造
  - [x] SubTask 4.1: 修改构造函数，新增 `parse_mode` 参数（默认从settings读取 `UI_PARSER_MODE`）
  - [x] SubTask 4.2: 新增 `TEXT_STRUCTURE_PROMPT` 类常量，用于OCR文本结构化
  - [x] SubTask 4.3: 实现 `_extract_text_with_ocr(image_bytes)` 方法，调用OCR提取器
  - [x] SubTask 4.4: 实现 `_structure_text_with_llm(ocr_text, screen_name_hint)` 方法，调用 `analyze_text` 结构化
  - [x] SubTask 4.5: 修改 `parse_single_screen` 方法，根据 `parse_mode` 选择解析路径
  - [x] SubTask 4.6: 实现text模式解析失败时自动降级到vision模式的逻辑
  - [x] SubTask 4.7: 修改 `parse_multiple_screen_flows` 方法，text模式下使用纯文本LLM调用

- [x] Task 5: ui_spec_parse_pipeline适配改造
  - [x] SubTask 5.1: 修改 `app/services/ui_spec_parse_pipeline.py`，传递 `parse_mode` 参数给UISpecParser
  - [x] SubTask 5.2: 在pipeline的解析报告元数据中记录使用的解析模式

- [x] Task 6: case_quality_analyzer清理
  - [x] SubTask 6.1: 移除 `app/services/case_quality_analyzer.py` 中的 `ai_vision_calls` 字段
  - [x] SubTask 6.2: 移除 `need_vision_steps` 计算逻辑和相关成本估算代码
  - [x] SubTask 6.3: 清理 `CostAnalysis` dataclass中的视觉调用相关字段

- [x] Task 7: 前端UI原型解析界面增加模式切换
  - [x] SubTask 7.1: 在 `src/views/requirement/ui-prototype.vue` 解析对话框中增加"解析模式"选择器
  - [x] SubTask 7.2: 选项包含"文本模式（推荐，成本低）"和"视觉模型模式（精度高，成本高）"
  - [x] SubTask 7.3: 选择视觉模型模式时显示费用提示
  - [x] SubTask 7.4: 将选择的模式传递给后端API

- [x] Task 8: 后端API适配解析模式参数
  - [x] SubTask 8.1: 修改UI原型解析相关API端点，接收 `parse_mode` 参数
  - [x] SubTask 8.2: 将 `parse_mode` 传递给UISpecParser

# Task Dependencies

- [Task 2] depends on [Task 1] — analyze_text方法需要确认配置
- [Task 3] is independent — OCR提取器可独立开发
- [Task 4] depends on [Task 2, Task 3] — 双模式改造依赖OCR提取器和analyze_text方法
- [Task 5] depends on [Task 4] — pipeline适配依赖UISpecParser改造
- [Task 6] is independent — 清理工作可独立进行
- [Task 7] is independent — 前端改造可独立进行
- [Task 8] depends on [Task 4] — API适配依赖UISpecParser改造
