### 10.8 前端用户体验设计

上下文精准化不能只在后端静默发生，前端需要让测试人员清楚知道"本次生成是否可信、缺什么、引用了什么、下一步怎么处理"。

> **已实现**：`ContextHealthPanel.vue` 展示完整性评分和 warnings，`EvidenceRefsPanel.vue` 展示审计信息，`CaseRefresh.vue` 保鲜建议页面，`ContextSelectPanel.vue` 无 UI 原型图体验优化，`GenerateCaseConfigForm.vue` ui_automation 确认弹窗。