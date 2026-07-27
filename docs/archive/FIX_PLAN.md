# AI TestMaster 代码问题修复方案

> 基于交叉验证后的13个确认问题，逐一制定修复方案。

---

## P0-1: AI客户端双轨制 — 统一为体系B

### 目标
将 `app/utils/ai_client*` (体系A) 的调用方迁移到 `app/ai/` (体系B)，最终删除体系A。

### 影响范围
- 体系A调用方 (6处):
  - `app/api/v1/endpoints/test_case_ai_generate/_generate.py:28`
  - `app/api/v1/endpoints/test_case_ai_stream.py:40`
  - `app/api/v1/endpoints/test_case_ai_generate/_precondition.py:15`
  - `app/api/v1/endpoints/test_point_import.py:44`
  - `app/api/v1/endpoints/test_point_import_stream.py:30`
  - `app/services/test_case_generation/validate_mixin.py:519`
  - `app/services/case_refresh_service.py:306`

- 体系A核心依赖 `ai_client_core` 的模块 (17处):
  - `app/ai/openai_client.py:146,210,297` (反向依赖，需优先处理)
  - `app/services/ai_failure.py:189,295`
  - `app/services/ui_spec_parser/ocr_mixin.py:34`
  - `app/services/xmind_ai_parser/_parser.py:13`

### 修复步骤

**Step 1: 统一异常类到 `app/ai/`**
1. 将 `app/utils/ai_client_core.py` 中的 `AIServiceError` + 7个子类 迁移到 `app/ai/error_codes.py`
2. 保留 `app/utils/ai_client_core.py` 中的 `_detect_ai_error()` 函数，改为从 `app/ai/error_codes.py` import
3. 更新 `app/ai/openai_client.py` 的 import 路径

**Step 2: 迁移体系A的缓存逻辑到体系B**
1. 将 `AIClientBase` 的 LRU缓存逻辑抽取为独立的 `app/ai/cache.py`
2. 在 `OpenAIClient` 中可选启用缓存（通过构造参数 `enable_cache=True`）

**Step 3: 逐步迁移调用方**
按依赖顺序迁移：
1. 先迁移 `app/services/` 内部的调用方
2. 再迁移 `app/api/v1/endpoints/` 的调用方
3. 每个文件迁移后运行 `pytest tests/ -x` 验证

**Step 4: 删除体系A**
1. 删除 `app/utils/ai_client*.py` (5个单文件)
2. 删除 `app/utils/ai_client_parser/` (3个文件)
3. 删除 `app/utils/ai_client_stream/` (2个文件)
4. 删除 `app/utils/ai_client_enhanced/` (3个文件)
5. 删除 `app/utils/ai_client_prompt.py`
6. 删除 `app/utils/ai_client_formatter.py`
7. 删除 `app/utils/ai_client_test_case.py`

### 验证
```bash
# 每步迁移后
pytest tests/ -x --timeout=60
# 最终
grep -r "from app.utils.ai_client" app/  # 应返回0结果
```

---

## P0-2: test_execution_engine 35个Mixin — 按职责合并

### 目标
将35个Mixin合并为8-10个高内聚模块。

### 当前结构 → 目标结构

| 当前文件 | 目标文件 | 合并逻辑 |
|----------|----------|----------|
| `action_executor_basic_mixin.py` | `action_executor.py` | 合并 |
| `action_executor_complex_mixin.py` | `action_executor.py` | 合并 |
| `action_executor_hover_select_mixin.py` | `action_executor.py` | 合并 |
| `action_executor_input_click_mixin.py` | `action_executor.py` | 合并 |
| `action_executor_verify_captcha_mixin.py` | `action_executor.py` | 合并 |
| `action_executor_mixin.py` | `action_executor.py` | 保留为组合入口 |
| `self_healing_strategy_mixin.py` | `self_healing.py` | 合并 |
| `self_healing_execute_mixin.py` | `self_healing.py` | 合并 |
| `self_healing_stagehand_mixin.py` | `self_healing.py` | 合并 |
| `self_healing_utils_mixin.py` | `self_healing.py` | 合并 |
| `dependency_resolution_mixin/_snapshot.py` | `dependency_resolution.py` | 合并 |
| `dependency_resolution_mixin/_graph.py` | `dependency_resolution.py` | 合并 |
| `dependency_resolution_mixin/_navigation.py` | `dependency_resolution.py` | 合并 |
| `dependency_resolution_mixin/_orchestration.py` | `dependency_resolution.py` | 合并 |
| `task_executor_mixin/` | `task_executor.py` | 合并子包为单文件 |
| `task_batch_executor_mixin/` | `task_batch_executor.py` | 合并子包为单文件 |
| `api_setup_mixin/` | `api_setup.py` | 合并子包为单文件 |
| `ai_recognition_mixin.py` | 保留 | 不变 |
| `precondition_mixin.py` | 保留 | 不变 |
| `step_executor_mixin.py` | 保留 | 不变 |
| `structured_assertion_mixin.py` | 保留 | 不变 |
| `test_data_mixin.py` | 保留 | 不变 |

### 修复步骤

**Step 1: 合并 action_executor 系列 (6→1)**
1. 创建 `action_executor.py`，将6个Mixin的内容合并为一个 `ActionExecutor` 类
2. 修复命名冲突：统一 `_ExecutorMixin` 为不同名称或合并
3. 更新 `__init__.py` 的 import
4. 删除旧文件和临时文件 `.tmp`

**Step 2: 合并 self_healing 系列 (4→1)**
1. 创建 `self_healing.py`，将4个Mixin合并
2. 按功能分组：strategy + execute + stagehand + utils

**Step 3: 合并 dependency_resolution 系列 (4→1)**
1. 创建 `dependency_resolution.py`，将4个子文件合并

**Step 4: 合并 task_executor 和 task_batch_executor**
1. 各自合并子包为单文件

**Step 5: 合并 api_setup**
1. 合并子包为单文件

**Step 6: 更新 `__init__.py` 和清理**
1. 更新 `TestExecutionEngineV2` 的继承列表
2. 删除旧目录和文件
3. 删除 `.tmp` 文件

### 验证
```bash
pytest tests/ -x --timeout=120
grep -r "from app.services.test_execution_engine.action_executor_" app/  # 应返回0
```

---

## P1-1: AI客户端7层拆分 — 合并为3个文件

### 目标
将 `app/utils/ai_client*` 的11个文件合并为：
- `app/utils/ai_client.py` — Facade入口 + 核心类
- `app/utils/ai_client_helpers.py` — 解析/格式化/提示词等辅助函数
- 删除 `ai_client_core.py`, `ai_client_parser/`, `ai_client_stream/`, `ai_client_enhanced/`, `ai_client_prompt.py`, `ai_client_formatter.py`, `ai_client_test_case.py`

### 修复步骤

**Step 1: 合并核心逻辑**
1. 将 `ai_client_core.py` 的 `AIClientBase` + 缓存 + 异常类 合并到 `ai_client.py`
2. 将 `ai_client_test_case.py` 的 `AITestCaseMixin` 合并到 `ai_client.py`
3. 将 `ai_client_stream/` 的 `AIStreamMixin` 合并到 `ai_client.py`

**Step 2: 合并辅助函数**
1. 将 `ai_client_parser/` 的解析函数合并到 `ai_client_helpers.py`
2. 将 `ai_client_prompt.py` 的提示词函数合并到 `ai_client_helpers.py`
3. 将 `ai_client_formatter.py` 的格式化函数合并到 `ai_client_helpers.py`
4. 将 `ai_client_enhanced/` 的增强函数合并到 `ai_client_helpers.py`

**Step 3: 更新 import**
1. 更新所有 `from app.utils.ai_client_core import` 为 `from app.utils.ai_client import`
2. 更新所有 `from app.utils.ai_client_parser import` 为 `from app.utils.ai_client_helpers import`

**Step 4: 清理**
1. 删除7个旧文件/目录
2. 更新 `ai_client.py` 的 `__all__` 导出列表

### 验证
```bash
pytest tests/ -x
grep -r "from app.utils.ai_client_core\|from app.utils.ai_client_parser\|from app.utils.ai_client_stream\|from app.utils.ai_client_enhanced\|from app.utils.ai_client_prompt\|from app.utils.ai_client_formatter\|from app.utils.ai_client_test_case" app/  # 应返回0
```

---

## P1-2: XMind三重实现 — 统一入口

### 目标
统一为单一入口 `XmindService`，内部根据模式选择解析器。

### 当前依赖
- `app/api/v1/endpoints/test_point_import.py` — 同时 import 三个解析器
- `app/api/v1/endpoints/test_point_import_stream.py` — import 两个解析器
- `app/api/v1/endpoints/history_asset.py` — import `xmind_parser`
- `app/services/file_parser.py` — import `xmind_parser`
- `app/services/xmind_case_parser/_parse.py` — import `xmind_parser`
- `app/services/xmind_ai_parser/_parsing.py` — import `xmind_case_parser`

### 修复步骤

**Step 1: 创建统一入口**
```python
# app/services/xmind_service.py
class XmindService:
    def parse(self, file_path, mode="basic"):
        if mode == "basic":
            return self._basic_parser.parse(file_path)
        elif mode == "ai":
            return self._ai_parser.parse(file_path)
        elif mode == "case":
            return self._case_parser.parse(file_path)
```

**Step 2: 迁移调用方**
1. 更新 `test_point_import.py` 使用 `XmindService`
2. 更新 `test_point_import_stream.py` 使用 `XmindService`
3. 更新 `history_asset.py` 使用 `XmindService`
4. 更新 `file_parser.py` 使用 `XmindService`

**Step 3: 内部依赖处理**
1. `xmind_case_parser` 依赖 `xmind_parser` 的 `XmindParseError` — 保留或内联
2. `xmind_ai_parser` 依赖 `xmind_case_parser` — 保留依赖关系

**Step 4: 可选：合并内部实现**
1. 将三个解析器的公共逻辑抽取到 `xmind_service.py`
2. 逐步删除冗余的内部文件

### 验证
```bash
pytest tests/ -x
grep -r "from app.services.xmind_parser import\|from app.services.xmind_ai_parser import\|from app.services.xmind_case_parser import" app/api/  # 应只返回 xmind_service
```

---

## P1-3: UI原型文件/子包同名冲突 — 删除死代码

### 目标
删除 `app/services/ui_spec_parser.py` (死代码)，保留 `app/services/ui_spec_parser/` (实际实现)。

### 修复步骤

**Step 1: 确认无引用**
grep确认 `ui_spec_parser.py` 无独立引用（已验证：0结果）

**Step 2: 删除文件**
```bash
rm app/services/ui_spec_parser.py
```

**Step 3: 处理其他UI解析器**
1. `ui_spec_ocr.py` — 检查是否被 `ui_spec_parser/ocr_mixin.py` 替代
2. `ui_spec_parse_pipeline.py` — 被2处引用，保留或合并到子包

### 验证
```bash
pytest tests/ -x
python -c "from app.services.ui_spec_parser import UISpecParser; print('OK')"
```

---

## P2-1: browser_controller v2后缀 — 重命名

### 目标
将 `browser_controller_v2.py` 重命名为 `browser_controller.py`。

### 影响范围 (12处)
```
app/services/test_execution_engine/__init__.py:66
app/services/test_execution_engine/task_batch_executor_mixin/_executor.py:86
app/services/precondition/browser_mixin.py:6
app/services/precondition/login_strategy_mixin.py:33
app/services/precondition/decorator.py:25
app/services/element_locator/__init__.py:28
app/services/batch_locator/batch_executor_mixin.py:10
app/utils/browser_controller_v2.py (自身)
app/utils/browser_controller_navigation.py (内部依赖)
app/utils/browser_controller_actions.py (内部依赖)
```

### 修复步骤

**Step 1: 重命名文件**
```bash
mv app/utils/browser_controller_v2.py app/utils/browser_controller.py
```

**Step 2: 批量替换 import**
```bash
# 所有文件
find app/ -name "*.py" -exec sed -i 's/browser_controller_v2/browser_controller/g' {} +
```

**Step 3: 验证**
```bash
pytest tests/ -x
grep -r "browser_controller_v2" app/  # 应返回0
```

---

## P2-2: case_quality_analyzer 死代码 — 删除

### 目标
删除 `app/services/case_quality_analyzer.py`。

### 修复步骤

**Step 1: 确认无引用**
grep确认0处引用（已验证）

**Step 2: 删除文件**
```bash
rm app/services/case_quality_analyzer.py
```

### 验证
```bash
pytest tests/ -x
```

---

## P2-3: execution_replay legacy — 完成迁移后删除

### 目标
完成legacy到新版本的迁移，删除5个legacy文件。

### 当前状态
- `legacy_service.py` 被2处引用: `execution_core/_analysis.py`, `execution_vis_video_replay.py`
- 其他legacy文件仅被 `legacy_service.py` 内部引用

### 修复步骤

**Step 1: 分析legacy vs 新版本功能差异**
1. 对比 `legacy_service.py` vs 新版本（如有对应service）
2. 确认新版本是否已覆盖legacy功能

**Step 2: 迁移调用方**
1. 更新 `execution_core/_analysis.py` 使用新版本
2. 更新 `execution_vis_video_replay.py` 使用新版本

**Step 3: 删除legacy文件**
```bash
rm app/services/execution_replay/legacy_*.py
```

### 验证
```bash
pytest tests/ -x
grep -r "legacy_service\|legacy_models\|legacy_playback\|legacy_query\|legacy_session" app/  # 应返回0
```

---

## P2-4: 测试数据同名类 — 重命名消除混淆

### 目标
将两个同名 `TestDataParameterizer` 类重命名以区分。

### 当前状态
- `test_data/parameterizer_mixin.py` → `TestDataParameterizer` — 解析 `{{variable}}` 语法
- `test_data_parameterizer/__init__.py` → `TestDataParameterizer` — 解析 `${namespace.param}` 语法

### 修复步骤

**Step 1: 重命名类**
1. `test_data/parameterizer_mixin.py`: `TestDataParameterizer` → `VariablePlaceholderParser`
2. `test_data_parameterizer/__init__.py`: `TestDataParameterizer` → `NamespaceParamParser`

**Step 2: 更新引用**
```bash
grep -r "from app.services.test_data.parameterizer_mixin import TestDataParameterizer" app/
grep -r "from app.services.test_data_parameterizer import TestDataParameterizer" app/
```

**Step 3: 更新 `test_data/__init__.py` 的导出**
```python
from app.services.test_data.parameterizer_mixin import VariablePlaceholderParser as TestDataParameterizer
```

### 验证
```bash
pytest tests/ -x
```

---

## P3-1: Pipeline Steps辅助文件 — 内聚到Step

### 目标
将11个 `_` 前缀辅助文件的函数内聚到对应的Step文件中。

### 修复步骤

**Step 1: 合并 `_coverage.py` 到 `_case_coverage.py`**
`_coverage.py` 只是re-export，删除即可。

**Step 2: 合并辅助函数**
1. `_parsing.py` → 合并到 `case_generation.py`
2. `_prompt.py` → 合并到 `case_generation.py`
3. `_dedup.py` → 合并到 `case_generation.py`
4. `_task_generators.py` → 合并到 `case_generation.py`
5. `_execution.py` → 合并到 `case_generation.py`
6. `_case_coverage.py` → 合并到 `case_generation.py`
7. `_scoring.py` → 合并到 `quality_gate.py`
8. `_signal_scoring.py` → 合并到 `quality_gate.py`
9. `_qg_coverage.py` → 合并到 `quality_gate.py`
10. `_regeneration.py` → 合并到 `quality_gate.py`

**Step 3: 删除旧文件**
删除所有 `_` 前缀文件。

### 验证
```bash
pytest tests/ -x
ls app/pipelines/steps/_*.py  # 应返回空
```

---

## P3-2: 空目录清理

### 目标
删除空目录。

### 修复步骤
```bash
rm -rf app/utils/unified_vision/
rm -rf app/services/case_generation/
```

### 验证
```bash
ls app/utils/unified_vision/  # 应不存在
ls app/services/case_generation/  # 应不存在
```

---

## P3-3: 向后兼容别名清理

### 目标
删除无用的别名和re-export。

### 修复步骤

**Step 1: 清理 `ai_client.py` 别名**
```python
# 删除这3行
_normalize_new_format = normalize_new_format
_normalize_old_format = normalize_old_format
_build_weight_model = build_weight_model
```

**Step 2: 清理 `case_quality_analyzer.py`**
已在 P2-2 中删除。

**Step 3: 清理 `ui_spec_parser.py`**
已在 P1-3 中删除。

### 验证
```bash
pytest tests/ -x
grep -r "_normalize_new_format\|_normalize_old_format\|_build_weight_model" app/  # 应返回0
```

---

## 执行顺序

| 阶段 | 问题 | 依赖 | 预计耗时 |
|------|------|------|----------|
| **Phase 1** | P2-2: 删除 case_quality_analyzer 死代码 | 无 | 5分钟 |
| **Phase 1** | P3-2: 删除空目录 | 无 | 2分钟 |
| **Phase 1** | P1-3: 删除 ui_spec_parser.py 死代码 | 无 | 5分钟 |
| **Phase 1** | P2-1: 重命名 browser_controller_v2 | 无 | 15分钟 |
| **Phase 1** | P3-3: 清理别名 | 无 | 10分钟 |
| **Phase 2** | P2-4: 重命名测试数据同名类 | 无 | 15分钟 |
| **Phase 2** | P1-2: 统一XMind入口 | 无 | 30分钟 |
| **Phase 3** | P0-1: AI客户端双轨制统一 | Phase 1 完成 | 2小时 |
| **Phase 3** | P1-1: AI客户端7层拆分合并 | P0-1 完成 | 1小时 |
| **Phase 4** | P0-2: 执行引擎35个Mixin合并 | 无 | 3小时 |
| **Phase 5** | P2-3: legacy文件清理 | 需确认功能覆盖 | 30分钟 |
| **Phase 5** | P3-1: Pipeline辅助文件合并 | 无 | 1小时 |

**总预计耗时**: 8-9小时

### 每个Phase完成后必须执行
```bash
pytest tests/ -x --timeout=120
npm run lint  # 前端如有改动
```
