import request from '../utils/request';

// 任务状态枚举
export enum TaskStatus {
  WAITING = 0,      // 等待执行
  RUNNING = 1,      // 执行中
  COMPLETED = 2,    // 执行完成
  FAILED = 3,       // 执行失败
  STOPPED = 4       // 已停止
}

// 执行状态枚举
export enum ExecutionStatus {
  PENDING = 0,      // 未执行
  RUNNING = 1,      // 执行中
  PASSED = 2,       // 通过
  FAILED = 3,       // 失败
  SKIPPED = 4,      // 跳过
  ERROR = 5         // 错误
}

// 测试任务相关API
const testTaskApi = {
  // 创建任务
  createTask: (data: {
    task_name: string;
    project_id: number;
    description?: string;
    case_ids: number[];
  }) => {
    return request.post('/api/v1/test_task', {
      project_id: data.project_id,
      task_name: data.task_name,
      description: data.description || '',
      case_ids: data.case_ids
    });
  },

  // 获取任务列表
  getTaskList: (params: {
    project_id?: number;
    status?: number | string;
    page?: number;
    page_size?: number;
  }) => {
    return request.get('/api/v1/test_task', { params });
  },

  // 获取任务详情
  getTaskDetail: (taskId: number, projectId?: number) => {
    return request.get(`/api/v1/test_task/${taskId}`, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 开始执行任务
  startTask: (taskId: number, projectId?: number, executionMode?: 'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart', mobileDeviceId?: string) => {
    return request.post(`/api/v1/test_task/${taskId}/start`, {
      execution_mode: executionMode,
      mobile_device_id: mobileDeviceId
    }, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 停止执行任务
  stopTask: (taskId: number, projectId?: number) => {
    return request.post(`/api/v1/test_task/${taskId}/stop`, null, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 获取任务执行结果
  getTaskResults: (taskId: number, projectId?: number) => {
    return request.get(`/api/v1/test_task/${taskId}/results`, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 执行任务
  runTask: (taskId: number, projectId?: number) => {
    return request.post(`/api/v1/test_task/${taskId}/run`, null, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 获取任务执行摘要
  getTaskSummary: (taskId: number, projectId?: number) => {
    return request.get(`/api/v1/test_task/${taskId}/summary`, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 删除任务
  deleteTask: (taskId: number, projectId?: number) => {
    return request.delete(`/api/v1/test_task/${taskId}`, {
      params: projectId ? { project_id: projectId } : {}
    });
  },

  // 获取项目下的测试用例（用于任务创建时选择）
  getProjectCases: (projectId: number, params?: { page?: number; page_size?: number }) => {
    return request.get('/api/v1/testCase', {
      params: { project_id: projectId, page: 1, page_size: 100, ...params }
    });
  }
};

export default testTaskApi;
