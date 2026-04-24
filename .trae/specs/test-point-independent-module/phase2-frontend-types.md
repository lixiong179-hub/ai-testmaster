# Phase 2: 前端类型定义与API封装（3个任务）

---

## T2.1: 完善前端类型定义 - testPoint.ts

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5 小时 |
| **依赖关系** | T0.2, T1.6 |
| **时间节点** | Phase2 第1个任务 |

---

### 目标描述

完善测试点TypeScript类型定义，确保与后端Schema一致，新增关联用例相关类型。

---

### 具体实施步骤

1. **打开类型定义文件
   - 打开 `src/types/testPoint.ts`

2. **检查现有类型定义
   - 查看已有的类型结构
   - 确认需要补充或修改的内容

3. **补充/完善类型定义

```typescript
// 测试点基础类型
export interface TestPoint {
  id: number;
  project_id: number;
  module: string;
  function: string;
  point: string;
  priority: number; // 1=高, 2=中, 3=低
  create_time: string;
  created_by?: string;
  requirement_id?: number;
  ai_prompt?: string;
  test_case_count?: number; // 关联用例数
}

// 测试点筛选条件
export interface TestPointFilter {
  module?: string;
  priority?: number | null;
  created_by?: string;
  requirement_id?: number | null;
  keyword?: string;
  skip?: number;
  limit?: number;
}

// 创建测试点请求
export interface TestPointForm {
  module: string;
  function: string;
  point: string;
  priority: number;
  ai_prompt?: string;
}

// 更新测试点请求
export interface TestPointUpdateForm {
  module?: string;
  function?: string;
  point?: string;
  priority?: number;
  ai_prompt?: string;
}

// 测试点列表响应
export interface TestPointListResponse {
  items: TestPoint[];
  total: number;
}

// 测试点关联用例请求
export interface TestPointTestCase {
  id: number;
  title: string;
  // 其他测试用例字段
}
}
```

4. **验证类型定义
   - 确保类型名称正确
   - 确保可选字段正确标记（?）
   - 确保与后端Schema一致

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 类型定义文件 | `src/types/testPoint.ts` |
| 后端Schema | `app/schemas/test_point.py` |
| 项目规范 | `.trae\rules\project_rules.md` |

---

### 预期成果标准（可量化）

- [ ] 类型定义文件内容完整
- [ ] 所有TypeScript类型正确定义
- [ ] 可选字段正确标记
- [ ] 与后端Schema保持一致
- [ ] 遵循项目规范

---

---

## T2.2: 完善前端API封装 - testPoint.ts

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.75 小时 |
| **依赖关系** | T2.1, T1.7-T1.10 |
| **时间节点** | Phase2 第2个任务 |

---

### 目标描述

完善测试点API封装，新增完整的CRUD方法，以及获取关联用例、批量生成用例等方法。

---

### 具体实施步骤

1. **打开API封装文件
   - 打开 `src/api/testPoint.ts`

2. **检查现有API封装
   - 查看已有的API方法
   - 确认需要补充或修改的内容

3. **补充/完善API方法

```typescript
import request from '@/utils/request';
import type {
  TestPoint,
  TestPointFilter,
  TestPointForm,
  TestPointUpdateForm,
  TestPointListResponse,
  TestPointTestCase
} from '@/types/testPoint';

// 获取测试点列表
export const getTestPointList = async (params: TestPointFilter): Promise<TestPointListResponse> => {
  return request.get('/api/v1/test-points', { params });
};

// 获取测试点详情
export const getTestPointDetail = async (id: number): Promise<TestPoint> => {
  return request.get(`/api/v1/test-points/${id}`);
};

// 获取测试点关联的测试用例
export const getTestPointTestCases = async (id: number, params?: any): Promise<TestPointTestCase[]> => {
  return request.get(`/api/v1/test-points/${id}/test-cases`, { params });
};

// 创建测试点
export const createTestPoint = async (data: TestPointForm): Promise<TestPoint> => {
  return request.post('/api/v1/test-points', data);
};

// 更新测试点
export const updateTestPoint = async (id: number, data: TestPointUpdateForm): Promise<TestPoint> => {
  return request.put(`/api/v1/test-points/${id}`, data);
};

// 删除测试点
export const deleteTestPoint = async (id: number): Promise<void> => {
  return request.delete(`/api/v1/test-points/${id}`);
};

// 批量删除测试点
export const batchDeleteTestPoints = async (ids: number[]): Promise<void> => {
  return request.delete('/api/v1/test-points/batch', { data: { ids } });
};

// 批量生成测试用例
export const batchGenerateTestCases = async (testPointIds: number[]): Promise<any> => {
  return request.post('/api/v1/test-points/batch-generate-cases', { test_point_ids: testPointIds });
};
```

4. **验证API封装
   - 确保使用统一的request封装
   - 确保TypeScript类型正确
   - 确保错误处理完整（try-catch）

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| API封装文件 | `src/api/testPoint.ts` |
| 参考API示例 | `src/api` 目录下的其他API文件 |
| 项目规范 | `.trae\rules\project_rules.md` |
| request封装 | 项目统一request工具 |

---

### 预期成果标准（可量化）

- [ ] API方法完整实现（8个方法）
- [ ] TypeScript类型正确
- [ ] 使用统一的request封装
- [ ] 错误处理完整
- [ ] 遵循项目规范

---

---

## T2.3: 创建测试点状态管理 - Pinia Store

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.75 小时 |
| **依赖关系** | T2.1, T2.2 |
| **时间节点** | Phase2 第3个任务 |

---

### 目标描述

创建测试点的Pinia状态管理Store，管理测试点列表、筛选条件、加载状态、选中项等。

---

### 具体实施步骤

1. **创建Store文件
   - 在 `src/store/` 目录下创建 `testPoint.ts`

2. **实现Store

```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { TestPoint, TestPointFilter } from '@/types/testPoint';
import * as testPointApi from '@/api/testPoint';

export const useTestPointStore = defineStore('testPoint', () => {
  // 状态
  const testPoints = ref<TestPoint[]>([]);
  const selectedTestPointIds = ref<number[]>([]);
  const filter = ref<TestPointFilter>({});
  const loading = ref(false);
  const total = ref(0);
  const viewMode = ref<'list' | 'grid'>('list');

  // 计算属性
  const selectedTestPoints = computed(() => 
    testPoints.value.filter(tp => selectedTestPointIds.value.includes(tp.id))
  );

  const highPriorityCount = computed(() => 
    testPoints.value.filter(tp => tp.priority === 1).length
  );

  const mediumPriorityCount = computed(() => 
    testPoints.value.filter(tp => tp.priority === 2).length
  );

  const lowPriorityCount = computed(() => 
    testPoints.value.filter(tp => tp.priority === 3).length
  );

  const totalTestCaseCount = computed(() => 
    testPoints.value.reduce((sum, tp) => sum + (tp.test_case_count || 0), 0)
  );

  // Actions
  const fetchTestPoints = async () => {
    loading.value = true;
    try {
      const res = await testPointApi.getTestPointList(filter.value);
      testPoints.value = res.items;
      total.value = res.total;
    } finally {
      loading.value = false;
    }
  };

  const setFilter = (newFilter: Partial<TestPointFilter>) => {
    filter.value = { ...filter.value, ...newFilter };
  };

  const toggleSelection = (id: number) => {
    const index = selectedTestPointIds.value.indexOf(id);
    if (index > -1) {
      selectedTestPointIds.value.splice(index, 1);
    } else {
      selectedTestPointIds.value.push(id);
    }
  };

  const clearSelection = () => {
    selectedTestPointIds.value = [];
  };

  const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'list' ? 'grid' : 'list';
  };

  return {
    // 状态
    testPoints,
    selectedTestPointIds,
    filter,
    loading,
    total,
    viewMode,
    // 计算属性
    selectedTestPoints,
    highPriorityCount,
    mediumPriorityCount,
    lowPriorityCount,
    totalTestCaseCount,
    // Actions
    fetchTestPoints,
    setFilter,
    toggleSelection,
    clearSelection,
    toggleViewMode
  };
});
```

3. **验证Store
   - 确保类型定义完整
   - 确保逻辑正确
   - 确保遵循项目规范

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考Store | `src/store` 目录下的其他Store |
| 项目规范 | `.trae\rules\project_rules.md` |
| Pinia文档 | https://pinia.vuejs.org/ |

---

### 预期成果标准（可量化）

- [ ] Store文件完整创建
- [ ] 状态定义完整
- [ ] Actions定义完整
- [ ] TypeScript类型正确
- [ ] 遵循项目规范

---

### 相关参考资料链接

| 参考 | 文件路径/链接 |
|------|-------------|
| 现有Store示例 | `src/store` 目录 |
| Pinia官方文档 | https://pinia.vuejs.org/ |
| 项目规范 | `.trae\rules\project_rules.md` |
