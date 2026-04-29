# 代码规范合规修复 Spec

## Why
项目代码规范检查发现当前代码存在大量违反项目开发规则的问题：测试覆盖率仅23%（要求≥95%）、37个文件超过300行限制、TypeScript中约100处使用any类型、Python中存在.format()字符串和TODO注释、日志泄露敏感信息等。需按优先级分阶段修复，确保代码质量符合规范。

## What Changes
- 修复TypeScript中所有`any`类型使用，替换为具体类型定义
- 修复Python中`.format()`字符串为f-string
- 移除所有TODO注释，未实现逻辑改为抛出NotImplementedError
- 修复日志中敏感信息泄露（密码坐标等）
- 拆分超过300行的文件为多个职责单一的模块
- 补充单元测试，将核心分支覆盖率从23%提升至≥95%
- 补充Python公开方法的类型注解与文档注释

## Impact
- Affected specs: 无直接影响其他spec
- Affected code:
  - `src/` 下约15个TypeScript文件（any类型修复）
  - `app/services/ui_spec_parser.py`、`app/utils/ai_client.py`、`app/utils/mcp_text_llm.py`、`app/utils/report_utils.py`（.format()修复）
  - `app/services/test_case_view_service.py`、`app/services/test_data_parameterizer.py`（TODO修复）
  - `app/services/precondition_service.py`（日志脱敏）
  - 37个超过300行的Python文件（拆分重构）
  - `tests/` 目录（新增测试用例）

## ADDED Requirements

### Requirement: TypeScript类型安全
系统 SHALL 在所有TypeScript代码中禁止使用`any`类型，所有变量、参数、返回值必须使用具体类型定义。

#### Scenario: API响应类型定义
- **WHEN** 定义API响应接口时
- **THEN** 必须使用泛型参数提供具体数据类型，禁止`ApiResponse<T = any>`

#### Scenario: 错误处理类型
- **WHEN** 捕获异常并处理错误时
- **THEN** 必须使用`unknown`类型捕获，通过类型守卫收窄，禁止`catch(error: any)`

#### Scenario: 动态对象类型
- **WHEN** 需要动态键值对象时
- **THEN** 必须定义具体接口或使用`Record<string, 具体类型>`，禁止`Record<string, any>`

### Requirement: Python字符串格式化规范
系统 SHALL 在所有Python代码中统一使用f-string进行字符串格式化，禁止使用`.format()`方法。

#### Scenario: 字符串拼接
- **WHEN** 需要格式化字符串时
- **THEN** 必须使用f-string语法（`f"..."`），禁止使用`"{}".format()`

### Requirement: 禁止TODO与空占位
系统 SHALL 禁止代码中存在TODO注释和空占位逻辑，未实现的功能必须抛出NotImplementedError。

#### Scenario: 发现TODO注释
- **WHEN** 代码中存在TODO标记的待实现逻辑时
- **THEN** 必须立即实现该逻辑或将其替换为`raise NotImplementedError("描述")`

### Requirement: 日志脱敏
系统 SHALL 确保所有日志输出不包含敏感信息（密码、密钥、token等），敏感字段必须脱敏处理。

#### Scenario: 记录包含敏感字段的日志
- **WHEN** 日志中需要记录包含敏感信息的数据时
- **THEN** 必须对敏感字段进行掩码处理（如`***`），禁止明文输出

### Requirement: 单文件行数限制
系统 SHALL 确保所有Python源文件不超过300行，超过限制的文件必须按职责拆分为多个模块。

#### Scenario: 文件超过300行
- **WHEN** 某个Python文件行数超过300行时
- **THEN** 必须按功能职责拆分为多个子模块，每个子模块不超过300行

#### Scenario: API端点文件拆分
- **WHEN** API端点文件超过300行时
- **THEN** 按功能域拆分为独立路由文件（如test_case_router.py、test_case_workflow_router.py），在原文件中聚合导入

#### Scenario: Service文件拆分
- **WHEN** Service文件超过300行时
- **THEN** 按业务功能拆分为子服务，主服务通过组合模式调用子服务

### Requirement: 测试覆盖率达标
系统 SHALL 确保核心分支测试覆盖率≥95%，每个模块必须配套正常、空值、异常、边界四类测试用例。

#### Scenario: 新增测试用例
- **WHEN** 为模块编写测试时
- **THEN** 必须覆盖正常路径、空值输入、异常场景、边界条件四种场景

#### Scenario: 使用真实测试库
- **WHEN** 执行测试时
- **THEN** 必须使用真实数据库连接，禁止Mock，测试完成后自动清理数据

### Requirement: Python公开方法类型注解
系统 SHALL 确保所有Python公开方法必须添加类型注解与文档注释。

#### Scenario: 定义公开方法
- **WHEN** 定义类或模块的公开方法时
- **THEN** 必须为所有参数和返回值添加类型注解，并添加文档字符串说明

## MODIFIED Requirements
无修改的已有需求。

## REMOVED Requirements
无移除的需求。
