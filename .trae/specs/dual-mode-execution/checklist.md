# Checklist - 双模式测试执行引擎

## 执行引擎改造

- [x] Task 1.1: execute_test_case() 方法添加 execution_mode 参数
- [x] Task 1.2: _execute_step() 方法添加 execution_mode 参数
- [x] Task 1.3: execution_mode 参数正确传递到执行逻辑

## 实时识别兜底逻辑

- [x] Task 2.1: 分析现有 _execute_step() 代码逻辑（无冗余）
- [x] Task 2.2: preprocess 模式：无 locator_record 时正确抛出 StepExecutionError
- [x] Task 2.3: realtime 模式：无 locator_record 时正确调用 smart_locate_element()
- [x] Task 2.4: smart 模式：优先使用预存定位，失败后AI兜底

## 代码复用验证

- [x] Task 3.1: _execute_with_self_healing() 可接受动态传入的 locator_record
- [x] Task 3.2: smart_locate_element() 返回格式与 get_locator() 一致
- [x] Task 3.3: 新增代码不重复实现已有功能

## 自动缓存机制

- [x] Task 4.1: realtime/smart 模式识别成功后调用 _save_realtime_locator 写入缓存
- [x] Task 4.2: source="ai_realtime" 正确标记缓存来源
- [x] Task 4.3: 缓存写入后后续执行可直接使用

## API 接口扩展

- [x] Task 5.1: 执行请求 schema 添加 execution_mode 字段
- [x] Task 5.2: API handler 正确传递 execution_mode 到执行引擎
- [x] Task 5.3: 三种模式参数正确处理

## 前端执行模式选择器

- [x] Task 6.1: 执行按钮弹出模式选择对话框
- [x] Task 6.2: 三种模式选项正确显示
- [x] Task 6.3: 选择的模式正确传递到后端 API

## 单元测试

- [x] Task 7.1: preprocess 模式异常抛出测试通过
- [x] Task 7.2: realtime 模式实时识别测试通过
- [x] Task 7.3: smart 模式缓存机制测试通过
- [x] Task 7.4: execution_mode 参数传递测试通过
- [x] Task 7.5: 单元测试覆盖率 >= 95%（核心逻辑100%覆盖）
- [x] Task 7.6: 单元测试通过率 = 100%（90/90通过）

## 代码评审修复

- [x] H-03: execution_mode 白名单校验（VALID_EXECUTION_MODES）
- [x] H-02: _save_realtime_locator 直接构建 ElementLocator，避免二次AI识别
- [x] H-04: 裸 except 替换为 except Exception，避免吞掉 KeyboardInterrupt

## 整体验证

- [x] 不引入任何新依赖（Midscene.js 或其他）
- [x] 不造成代码冗余和重复功能
- [x] 复用现有 unified_vision_model.py 能力
- [x] 复用现有 smart_locate_element() 能力
- [x] 复用现有 _execute_with_self_healing() 逻辑
