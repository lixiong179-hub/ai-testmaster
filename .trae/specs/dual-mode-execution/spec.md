# 双模式测试执行引擎 Spec

## Why

当前测试执行流程存在严重效率问题：
1. **必须预处理**：AI生成的测试用例是纯文字描述，无法直接执行，必须先批量补充元素定位信息
2. **用户操作繁琐**：需要2步操作（先预处理 → 再执行），增加了用户负担
3. **灵活性不足**：无法根据用例描述质量灵活选择执行方式

需要实现类似Midscene.js的能力：让用户选择执行模式——要么预处理确保准确率，要么跳过预处理直接实时AI识别执行。

**核心目标**：实现双模式执行能力，让用户根据用例描述质量和时间要求灵活选择：
- **预处理模式**：适合用例描述模糊、追求高准确率的场景
- **实时识别模式**：适合用例描述准确、追求快速执行的场景

## What Changes

- **新增双模式执行参数** — 执行接口支持 `execution_mode` 参数，区分预处理模式和实时识别模式
- **新增实时识别兜底逻辑** — 当无预存定位信息时，自动调用AI实时识别（不依赖预处理）
- **新增定位缓存机制** — 首次识别后缓存定位信息，后续执行复用，减少AI调用
- **复用现有能力** — 不引入Midscene.js，使用项目现有 `unified_vision_model.py` 和 `smart_locate_element()`
- **消除代码冗余** — 实时识别复用的逻辑与预处理模式共用，不重复实现

## Impact

- Affected specs: ui-automation-enhancement, batch-locator-optimization, ai-test-case-executability-optimization
- Affected code:
  - `app/services/test_execution_engine_v2.py` — 新增 execution_mode 参数，实时识别兜底逻辑
  - `app/services/element_locator_service.py` — 复用现有 smart_locate_element()，新增缓存机制
  - `app/api/v1/endpoints/execution.py` — 新增 execution_mode 接口参数
  - `app/models/test_case.py` — 新增 locator_cache 缓存表结构
  - `app/services/locator_cache_service.py` — 新增定位缓存服务（复用现有定位逻辑）

## ADDED Requirements

### Requirement: 执行模式选择

系统 SHALL 支持用户在执行测试用例时选择执行模式。

#### Scenario: 预处理模式执行
- **GIVEN** 用户选择"预处理模式"
- **AND** 测试用例缺少元素定位信息
- **WHEN** 用户执行该用例
- **THEN** 系统提示"请先批量补充元素定位信息"
- **AND** 只有定位信息完整的用例才能执行

#### Scenario: 实时识别模式执行
- **GIVEN** 用户选择"实时识别模式"
- **AND** 测试用例只有纯文字描述
- **WHEN** 用户执行该用例
- **THEN** 系统跳过预处理步骤
- **AND** 执行时自动调用AI实时识别元素位置
- **AND** 无需预存定位信息

#### Scenario: 混合模式任务执行
- **GIVEN** 测试任务包含多个用例
- **AND** 部分用例有定位信息，部分没有
- **WHEN** 用户选择"实时识别模式"执行任务
- **THEN** 有定位信息的用例使用预存定位快速执行
- **AND** 无定位信息的用例自动调用AI实时识别

### Requirement: 实时识别兜底机制

系统 SHALL 当执行步骤无预存定位信息时，自动调用AI进行实时元素识别。

#### Scenario: 步骤执行时无预存定位
- **GIVEN** 执行步骤编号为5的操作"点击提交按钮"
- **AND** 该步骤无预存的 ElementLocator 记录
- **WHEN** 执行引擎执行该步骤
- **THEN** 调用 `smart_locate_element(action_description="点击提交按钮")`
- **AND** AI截取当前页面截图
- **AND** AI根据文字描述识别目标元素坐标
- **AND** 执行点击操作

#### Scenario: 实时识别成功
- **GIVEN** AI实时识别到"提交"按钮坐标 (x=500, y=300)
- **WHEN** 执行引擎获取到坐标
- **THEN** 使用坐标执行点击操作
- **AND** 等待页面响应
- **AND** 标记步骤执行成功

#### Scenario: 实时识别失败
- **GIVEN** AI实时识别返回空结果或置信度 < 0.7
- **WHEN** 执行引擎获取识别结果
- **THEN** 标记步骤执行失败
- **AND** 记录失败原因"AI无法识别目标元素"
- **AND** 截取当前页面截图供分析

#### Scenario: 实时识别成功时自动缓存
- **GIVEN** AI实时识别成功定位到元素
- **WHEN** 识别结果置信度 >= 0.8
- **THEN** 自动调用 `record_locator()` 保存定位信息到数据库
- **AND** 下次执行时可直接使用缓存的定位信息

### Requirement: 定位缓存机制

系统 SHALL 缓存元素定位信息以减少重复的AI调用。

#### Scenario: 首次执行创建缓存
- **GIVEN** 首次执行步骤"点击提交按钮"
- **AND** 无历史缓存
- **WHEN** AI实时识别成功
- **THEN** 将定位信息存入 ElementLocator 表
- **AND** 设置 source="ai_realtime"

#### Scenario: 后续执行命中缓存
- **GIVEN** 之前执行过步骤"点击提交按钮"
- **AND** ElementLocator 表中已有该步骤的记录
- **WHEN** 再次执行该步骤
- **THEN** 优先使用缓存的定位信息（CSS/XPath/坐标）
- **AND** 不再调用AI实时识别

#### Scenario: 缓存失效时重新识别
- **GIVEN** 缓存的定位信息存在
- **WHEN** 使用缓存执行操作失败（元素不存在）
- **THEN** 自动降级到AI实时识别
- **AND** 识别成功则更新缓存
- **AND** 记录缓存失效次数

### Requirement: 智能执行策略

系统 SHALL 根据定位信息可用性和执行历史智能选择执行路径。

#### Scenario: 执行策略：严格模式（预处理模式）
- **GIVEN** 用户选择预处理模式
- **WHEN** 执行引擎处理步骤
- **THEN** 必须有预存 ElementLocator 才能执行
- **AND** 无预存定位时标记步骤失败

#### Scenario: 执行策略：实时模式
- **GIVEN** 用户选择实时识别模式
- **WHEN** 执行引擎处理步骤
- **THEN** 有预存定位时使用预存定位
- **AND** 无预存定位时调用AI实时识别

#### Scenario: 执行策略：智能模式（默认）
- **GIVEN** 用户选择智能模式（默认）
- **WHEN** 执行引擎处理步骤
- **THEN** 优先使用预存定位（快速，0成本）
- **AND** 预存定位失败时调用AI实时识别
- **AND** 实时识别成功则更新缓存

### Requirement: 执行接口参数扩展

系统 SHALL 在执行接口中支持 execution_mode 参数。

#### Scenario: 调用预处理模式执行
```http
POST /api/v1/execution/run
{
  "test_case_id": 123,
  "execution_mode": "preprocess"
}
```

#### Scenario: 调用实时识别模式执行
```http
POST /api/v1/execution/run
{
  "test_case_id": 123,
  "execution_mode": "realtime"
}
```

#### Scenario: 调用智能模式执行（默认）
```http
POST /api/v1/execution/run
{
  "test_case_id": 123,
  "execution_mode": "smart"  // 默认值
}
```

### Requirement: 前端执行模式选择器

系统 SHALL 在前端提供执行模式选择器。

#### Scenario: 用例执行页面模式选择
- **GIVEN** 用户在用例执行页面
- **WHEN** 用户点击"执行"按钮
- **THEN** 弹出执行选项对话框
- **AND** 包含执行模式选择：
  ```
  执行模式：
  ○ 预处理模式（需要先补充元素定位）
  ● 实时识别模式（直接执行，可能准确率较低）
  ○ 智能模式（推荐，优先缓存，失败后实时识别）
  ```

#### Scenario: 任务执行页面模式选择
- **GIVEN** 用户在任务执行页面
- **WHEN** 用户点击"执行任务"按钮
- **THEN** 弹出执行选项对话框
- **AND** 包含执行模式选择（应用于所有用例）

### Requirement: 定位信息完整性检查

系统 SHALL 在预处理模式下执行前检查定位信息完整性。

#### Scenario: 预处理模式检测到缺失定位
- **GIVEN** 用户选择预处理模式执行用例
- **WHEN** 系统检查用例步骤
- **THEN** 发现步骤5缺少 ElementLocator
- **AND** 返回错误"步骤5尚未补充元素定位信息"
- **AND** 提示用户前往批量定位页面补充

#### Scenario: 实时识别模式跳过完整性检查
- **GIVEN** 用户选择实时识别模式执行用例
- **WHEN** 系统接收执行请求
- **THEN** 不检查 ElementLocator 是否存在
- **AND** 直接开始执行
- **AND** 无定位的步骤自动实时识别

## MODIFIED Requirements

### Requirement: 执行引擎步骤执行逻辑改造

**原实现** (`test_execution_engine_v2.py` 第503-520行):
```python
if locator_record:
    await self._execute_with_self_healing(...)
else:
    await self._execute_action_by_type(...)  # 无预存定位时不调用AI
```

**新实现**:
```python
async def _execute_step(self, step, execution_mode: str = "smart"):
    locator_record = self.locator_service.get_locator(step.id)

    if execution_mode == "preprocess":
        # 预处理模式：必须有预存定位
        if not locator_record:
            raise StepExecutionError("步骤缺少元素定位信息，请先批量补充")
        await self._execute_with_self_healing(...)
    elif execution_mode == "realtime":
        # 实时识别模式：无预存定位时AI实时识别
        if not locator_record:
            locator_record = await self.locator_service.smart_locate_element(
                action_description=step.action,
                page_title=current_page_title
            )
        await self._execute_with_locator_or_realtime(locator_record, ...)
    else:  # smart (默认)
        # 智能模式：优先缓存，失败后AI兜底
        if not locator_record:
            locator_record = await self.locator_service.smart_locate_element(...)
        await self._execute_with_self_healing(...)
```

**Migration**:
- 新增 `execution_mode` 参数，默认为 "smart"
- 不删除现有 `_execute_with_self_healing` 逻辑，复用
- 仅在无 `locator_record` 时根据模式选择处理方式

### Requirement: ElementLocatorService 复用

**原实现**: `smart_locate_element()` 仅作为 CSS 选择器失败后的兜底

**新实现**:
- `smart_locate_element()` 保持不变，作为兜底逻辑
- 新增 `realtime_locate_element()` 方法，专门用于实时识别场景
- 两个方法内部都调用 `_recognize_element()`，不重复实现AI识别逻辑

## 技术方案

### 双模式执行流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    测试用例执行流程                               │
│                                                                 │
│  1. 接收执行请求 (execution_mode: preprocess/realtime/smart)    │
│                                                                 │
│  2. 遍历测试步骤                                                │
│     │                                                          │
│     ├─ 3. 获取预存 ElementLocator                               │
│     │                                                          │
│     ├─ 4. 根据 execution_mode 执行                              │
│     │                                                          │
│     │   ┌─────────────────────────────────────────────┐        │
│     │   │  preprocess 模式                            │        │
│     │   │  ├─ locator_record 存在 → 使用预存定位     │        │
│     │   │  └─ locator_record 不存在 → 标记失败       │        │
│     │   └─────────────────────────────────────────────┘        │
│     │                                                          │
│     │   ┌─────────────────────────────────────────────┐        │
│     │   │  realtime 模式                              │        │
│     │   │  ├─ locator_record 存在 → 使用预存定位     │        │
│     │   │  └─ locator_record 不存在 → AI实时识别    │        │
│     │   └─────────────────────────────────────────────┘        │
│     │                                                          │
│     │   ┌─────────────────────────────────────────────┐        │
│     │   │  smart 模式（默认）                          │        │
│     │   │  ├─ locator_record 存在 → 使用预存定位     │        │
│     │   │  ├─ locator_record 不存在 → AI实时识别    │        │
│     │   │  └─ 识别成功 → 自动缓存定位信息           │        │
│     │   └─────────────────────────────────────────────┘        │
│     │                                                          │
│     └─ 5. 执行操作并记录结果                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 缓存机制流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    定位缓存流程                                  │
│                                                                 │
│  首次执行 (无缓存):                                              │
│  ┌─────────────────────────────────────────────┐               │
│  │ 步骤执行 → AI实时识别 → 成功 → 写入缓存     │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
│  后续执行 (有缓存):                                              │
│  ┌─────────────────────────────────────────────┐               │
│  │ 步骤执行 → 使用缓存定位 → 成功 → 完成       │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
│  缓存失效时:                                                     │
│  ┌─────────────────────────────────────────────┐               │
│  │ 缓存定位 → 执行失败 → AI实时识别 → 更新缓存 │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 成本对比

| 场景 | 预处理模式 | 实时识别模式 | 智能模式 |
|------|-----------|-------------|---------|
| **首次执行** | 预处理1次AI + 执行0次AI | 执行1次AI | 执行1次AI |
| **后续执行** | 执行0次AI | 执行1次AI | 执行0次AI（命中缓存） |
| **平均AI调用** | 0.1次/步骤 | 1次/步骤 | 0.2次/步骤 |
| **用户操作** | 2步（预处理+执行） | 1步（直接执行） | 1步（直接执行） |
| **准确率** | 高 | 中（依赖描述质量） | 高 |

### 复用现有代码设计

```
不新增 Midscene.js 依赖，复用项目现有能力：

unified_vision_model.py          → AI视觉识别能力（已实现）
element_locator_service.py        → smart_locate_element()（已实现）
test_execution_engine_v2.py       → 执行引擎改造（核心改动）

新增改动：
1. execution_mode 参数传递
2. 无 locator_record 时的实时识别分支
3. 复用现有 _execute_with_self_healing 逻辑
```

### 与 Midscene.js 能力对比

| 能力 | Midscene.js | 本方案 |
|------|-------------|--------|
| 自然语言执行 | ✅ aiAction() | ✅ 实时识别模式 |
| 无需预定义选择器 | ✅ | ✅ |
| 缓存机制 | ✅ XPath缓存 | ✅ ElementLocator复用 |
| 多模型支持 | GPT-4o/Qwen等 | Kimi/智谱/通义千问等 |
| 技术栈 | Node.js | Python（项目现有） |
| **引入新依赖** | ❌ | ❌ |

## 交付标准

### 功能验收

1. ✅ 执行接口支持 `execution_mode` 参数（preprocess/realtime/smart）
2. ✅ 预处理模式：无不完整定位信息的用例无法执行
3. ✅ 实时识别模式：无预存定位时自动调用AI实时识别
4. ✅ 智能模式：优先使用缓存，失败后自动降级到AI实时识别
5. ✅ 实时识别成功时自动写入缓存（置信度 >= 0.8）
6. ✅ 缓存命中时跳过AI调用
7. ✅ 前端提供执行模式选择器
8. ✅ 不引入任何新依赖，复用现有代码

### 质量标准

1. ✅ 不造成代码冗余和重复功能
2. ✅ 复用现有 `smart_locate_element()` 和 `_recognize_element()`
3. ✅ 复用现有 `_execute_with_self_healing()` 逻辑
4. ✅ 单元测试覆盖率 >= 95%
5. ✅ 单元测试通过率 = 100%
