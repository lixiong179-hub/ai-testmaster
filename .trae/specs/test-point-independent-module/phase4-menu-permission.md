# Phase 4: 菜单配置与权限集成（2个任务）

---

## T4.1: 配置侧边栏菜单 - 添加测试点管理入口

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5 小时 |
| **依赖关系** | T3.1 |
| **时间节点** | Phase4 第1个任务 |

---

### 目标描述

在侧边栏菜单中添加"测试点管理"入口，使其可以正常访问。

---

### 具体实施步骤

1. **查找菜单配置文件
   - 在项目中搜索侧边栏菜单配置，通常位置在：
     - `src/router/index.ts` 或 `src/router/index.ts`
     - `src/layout/components/Sidebar/index.vue`
     - `src/constants/menu.ts` 或类似文件

2. **查看现有菜单结构
   - 了解菜单项的定义格式
   - 查看"测试用例"菜单的配置作为参考

3. **添加"测试点管理"菜单

```typescript
// 示例菜单配置（根据实际项目调整）
{
  path: '/test-point',
  name: 'TestPoint',
  component: () => import('@/views/test-point/TestPointList.vue'),
  meta: {
    title: '测试点管理',
    icon: 'Document', // 或其他合适的图标
    permission: ['test_point:read'] // 权限标识
  }
}
```

4. **在合适的菜单组中添加新菜单项
   - 建议放在"测试用例"或"需求分析"同一组中
   - 确保菜单层级正确

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 路由/菜单配置文件 | 项目现有的路由或菜单配置 |
| 参考菜单项 | "测试用例"菜单配置 |

---

### 预期成果标准（可量化）

- [ ] 菜单项正确添加到侧边栏
- [ ] 点击菜单项可以正常跳转
- [ ] 页面可以正常显示
- [ ] 菜单图标合适且符合项目风格
- [ ] 菜单层级正确

---

---

## T4.2: 前端权限控制集成

| 属性 | 内容 |
|------|------|
| **优先级** | 🟡 中 |
| **负责人** | 前端开发 |
| **预计工时** | 0.75 小时 |
| **依赖关系** | T4.1, T1.9 |
| **时间节点** | Phase4 第2个任务 |

---

### 目标描述

在前端集成权限控制，确保测试点相关操作的权限校验正常工作。

---

### 具体实施步骤

1. **查找现有权限系统
   - 在项目中搜索权限相关代码
   - 查看现有权限检查的实现方式
   - 查看权限Store或工具函数

2. **在页面中集成权限控制

```typescript
// 示例权限检查（根据实际项目调整）
import { usePermissionStore } from '@/store/permission';

const permissionStore = usePermissionStore();

const canCreate = computed(() => 
  permissionStore.hasPermission('test_point:create')
);
const canUpdate = computed(() => 
  permissionStore.hasPermission('test_point:update')
);
const canDelete = computed(() => 
  permissionStore.hasPermission('test_point:delete')
);
```

3. **根据权限控制按钮显示

```vue
<!-- 根据权限控制按钮显示 -->
<el-button
  v-if="selectedProjectId && canCreate"
  type="primary"
  @click="openCreateDialog"
>
  <el-icon><Plus /></el-icon>
  新增测试点
</el-button>

<!-- 在表格操作列中 -->
<template #default="{ row }">
  <el-button type="primary" size="small" @click="showTestCases(row)">
    <el-icon><List /></el-icon>
    查看用例
  </el-button>
  <el-button v-if="canCreate" type="success" size="small" @click="handleGenerateSingle(row)">
    <el-icon><MagicStick /></el-icon>
    生成用例
  </el-button>
  <el-button v-if="canUpdate" type="warning" size="small" @click="handleEdit(row)">
    <el-icon><Edit /></el-icon>
    编辑
  </el-button>
  <el-popconfirm v-if="canDelete" title="确定删除吗？" @confirm="handleDelete(row)">
    <template #reference>
      <el-button type="danger" size="small">
        <el-icon><Delete /></el-icon>
        删除
      </el-button>
    </template>
  </el-popconfirm>
</template>
```

4. **控制批量操作按钮

```vue
<!-- 批量操作按钮 -->
<div v-if="store.selectedTestPointIds.length > 0" class="batch-actions">
  <el-tag type="warning" class="batch-tag">
    已选择 {{ store.selectedTestPointIds.length }} 条
  </el-tag>
  <el-button v-if="canDelete" type="danger" @click="handleBatchDelete">
    <el-icon><Delete /></el-icon>
    批量删除
  </el-button>
  <el-button v-if="canCreate" type="primary" @click="handleBatchGenerate">
    <el-icon><MagicStick /></el-icon>
    批量生成用例
  </el-button>
  <el-button @click="store.clearSelection">
    取消选择
  </el-button>
</div>
```

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 现有权限系统 | 项目现有的权限实现 |
| 参考权限实现 | 其他页面的权限控制方式 |

---

### 预期成果标准（可量化）

- [ ] 权限控制正常工作
- [ ] 无权限时按钮隐藏或禁用
- [ ] 菜单权限控制正常
- [ ] 符合项目现有权限规范

---

### 相关参考资料链接

| 参考 | 文件路径 |
|------|---------|
| 项目规范 | `.trae\rules\project_rules.md` |
| 参考权限实现 | 其他页面的权限控制代码 |
