# UI原型解析结果增强展示 Spec

## Why

当前UI原型解析后端已支持丰富的结构化数据（elements、navigation、flows、layout_constraints、visual_style等），但前端仅展示AI摘要（summary）和基础统计（element_count、button_count），未能充分利用解析结果。用户无法查看具体的元素详情、跳转流程、布局约束等信息，降低了解析的价值。

## What Changes

- **预览弹窗增强** — 展示更丰富的解析结果结构化数据
- **元素详情折叠面板** — 展示elements数组（类型、标签、语义、位置等）
- **跳转流程区域** — 展示flows数据（预期跳转页面、触发动作）
- **布局约束展示** — 展示layout_constraints（对齐、间距、颜色对比等）
- **视觉风格展示** — 展示visual_style（背景色、主题色、圆角风格等）
- **页面布局美化** — 优化卡片和弹窗的信息层级和视觉效果

## Impact

- Affected specs: vision-model-optimization, ui-prototype-integration
- Affected code:
  - `src/views/requirement/ui-prototype.vue` — 预览弹窗重构，增加详情折叠面板

## ADDED Requirements

### Requirement: 预览弹窗增强展示

系统 SHALL 在UI原型图预览弹窗中展示更丰富的解析结果数据。

#### Scenario: 查看已解析屏幕的完整信息
- **GIVEN** 用户上传的UI原型图已完成解析
- **WHEN** 用户点击屏幕卡片打开预览
- **THEN** 弹窗展示：基础信息 + 元素详情 + 跳转流程 + 布局约束 + 视觉风格
- **AND** 信息分块展示，使用折叠面板组织

#### Scenario: 查看未解析屏幕的预览
- **GIVEN** 用户上传的UI原型图尚未解析
- **WHEN** 用户点击屏幕卡片打开预览
- **THEN** 弹窗仅展示基础信息（名称、状态）
- **AND** 提示"请先解析以查看详情"

### Requirement: 元素详情折叠面板

系统 SHALL 提供元素详情折叠面板，展示解析出的页面元素列表。

#### Scenario: 展示元素列表
- **GIVEN** 屏幕已解析并包含elements数据
- **WHEN** 用户展开"元素详情"折叠面板
- **THEN** 展示元素列表，每项包含：
  - 类型标签（button/input/text/icon等）
  - 标签文字
  - 语义描述
  - 位置（top_left/center/bottom_right等）
  - 交互性（可点击/不可点击）
  - 状态（normal/disabled/error等）
- **AND** 元素按位置排序（从上到下）

#### Scenario: 空元素列表处理
- **GIVEN** 屏幕已解析但elements为空
- **WHEN** 用户展开"元素详情"折叠面板
- **THEN** 提示"未识别到页面元素"

### Requirement: 跳转流程区域

系统 SHALL 展示解析出的页面跳转流程信息。

#### Scenario: 展示跳转流程
- **GIVEN** 屏幕已解析并包含flows数据
- **WHEN** 用户查看"跳转流程"区域
- **THEN** 展示：
  - 预期跳转页面列表
  - 触发动作列表
  - 返回按钮可见性
  - Tab栏内容（如有）

#### Scenario: 空流程数据处理
- **GIVEN** 屏幕已解析但flows为空
- **WHEN** 用户查看"跳转流程"区域
- **THEN** 提示"未识别到跳转流程"

### Requirement: 布局约束展示

系统 SHALL 展示解析出的布局约束信息。

#### Scenario: 展示布局约束列表
- **GIVEN** 屏幕已解析并包含layout_constraints数据
- **WHEN** 用户查看"布局约束"区域
- **THEN** 展示约束列表，每项包含：
  - 约束类型（alignment/spacing/sizing/color_contrast等）
  - 描述文字
  - 优先级（high/medium/low）
  - 可验证的检查点

### Requirement: 视觉风格展示

系统 SHALL 展示解析出的视觉风格信息。

#### Scenario: 展示视觉风格
- **GIVEN** 屏幕已解析并包含visual_style数据
- **WHEN** 用户查看"视觉风格"区域
- **THEN** 展示：
  - 背景色
  - 主题色
  - 圆角风格
  - 阴影使用情况

### Requirement: 页面布局美化

系统 SHALL 优化UI原型图页面的视觉层次和布局。

#### Scenario: 卡片信息优化
- **GIVEN** 屏幕卡片展示
- **WHEN** 用户查看屏幕列表
- **THEN** 卡片包含：
  - 缩略图
  - 屏幕名称
  - 解析状态标签
  - 元素数量统计（图标+数字）
  - 按钮数量统计
  - 输入框数量统计

#### Scenario: 弹窗布局优化
- **GIVEN** 预览弹窗展示
- **WHEN** 用户打开任意屏幕的预览
- **THEN** 布局分为：
  - 左侧：图片预览（60%宽度）
  - 右侧：信息面板（40%宽度）
  - 下方：可折叠的详情区域

## MODIFIED Requirements

### Requirement: 预览弹窗基础信息展示

**原实现**: 仅展示screen_name、prototype_name、parse_status、element_count、button_count、input_count、summary

**修改后**:
- 保留基础信息展示
- 增加元素数量、按钮数量、输入框数量的图标装饰
- AI摘要展示在信息面板顶部

## Design Guidelines

### 布局原则
- **信息分层**: 基础信息 > 元素详情 > 高级信息（布局/风格）
- **视觉层次**: 使用卡片、折叠面板、标签进行信息分组
- **留白适度**: 左右布局时保持适当间距

### 颜色规范
- 类型标签颜色：
  - button: 蓝色（primary）
  - input: 橙色（warning）
  - text: 灰色（info）
  - icon: 紫色（purple）
  - link: 青色（cyan）
  - 其他: 默认色

### 交互规范
- 折叠面板默认展开"元素详情"
- 其他详情面板默认折叠
- 元素列表最多显示20项，超出显示"查看更多"
