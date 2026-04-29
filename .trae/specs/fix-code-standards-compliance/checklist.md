# Checklist

## Phase 1: 语言规范与安全红线

- [ ] TypeScript request.ts中无`any`类型使用
- [ ] TypeScript API层文件（case.ts、uiPrototype.ts、testCaseView.ts、file.ts、testData.ts）中无`any`类型使用
- [ ] TypeScript Store层（task.ts、project.ts、case.ts、analysis.ts）中无`any`类型使用
- [ ] TypeScript Composables层（useResourceUpload.ts、useResourceOperations.ts、useResourceList.ts、useIterationManager.ts）中无`any`类型使用
- [ ] TypeScript工具层（websocket.ts、debounce.ts、permission.ts）中无`any`类型使用
- [ ] TypeScript类型定义（case.d.ts、testCase.ts）中无`any`类型使用
- [ ] `npx tsc --noEmit`编译通过无类型错误
- [ ] Python代码中无`.format()`字符串调用
- [ ] Python代码中无TODO/FIXME/HACK/XXX注释
- [ ] 日志中无明文敏感信息（密码、token、密钥等）

## Phase 2: 架构设计 - 文件拆分

- [ ] 所有Python源文件行数≤300行
- [ ] 800+行文件全部拆分完成且功能不变
- [ ] 500-800行文件全部拆分完成且功能不变
- [ ] 300-500行文件全部拆分完成且功能不变
- [ ] 拆分后API路由注册正确，所有端点可访问
- [ ] 拆分后Service层调用链完整，业务逻辑不变
- [ ] `python -m pytest tests/`全部通过

## Phase 3: 测试覆盖率

- [ ] pytest.ini中配置了`--cov-fail-under=95`阈值
- [ ] 测试使用真实数据库连接，禁止Mock
- [ ] 测试用例执行后自动清理测试数据
- [ ] Model层测试覆盖率≥95%
- [ ] Core层测试覆盖率≥95%
- [ ] Utils层测试覆盖率≥95%
- [ ] CRUD层测试覆盖率≥95%
- [ ] 总体测试覆盖率≥95%
- [ ] 每个模块配套正常、空值、异常、边界四类测试用例

## Phase 4: Python类型注解

- [ ] API端点所有公开方法有返回类型注解
- [ ] Service层所有公开方法有类型注解与文档注释
- [ ] Utils层所有工具函数有类型注解与文档注释
- [ ] CRUD层所有方法有类型注解与文档注释
- [ ] `mypy`类型检查通过（或`--ignore-missing-imports`模式下无错误）
