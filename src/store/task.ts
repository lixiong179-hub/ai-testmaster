import { defineStore } from 'pinia';
import testTaskApi, { TaskStatus, ExecutionStatus } from '../api/testTask';

// 导出枚举供组件使用
export { TaskStatus, ExecutionStatus };

// 任务类型
export interface TestTask {
  id: number;
  task_name: string;
  project_id: number;
  description?: string;
  case_ids: number[];
  executor_id: number;
  status: number;
  start_time?: string;
  end_time?: string;
  success_count: number;
  fail_count: number;
  total_count: number;
  progress: number;
  create_time: string;
  update_time?: string;
}

// 执行结果类型
export interface TestResult {
  id: number;
  task_id: number;
  project_id: number;
  case_id: number;
  case_no: string;
  exec_status: number;
  exec_time: string;
  exec_log?: string;
  error_msg?: string;
  screenshot_url?: string;
  create_time: string;
  update_time?: string;
}

// 步骤执行结果类型
export interface StepResult {
  step_number: number;
  action: string;
  status: string;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  error_message?: string;
  execution_detail?: string;
}

// 任务执行结果详情
export interface TaskExecutionResult {
  execution_id: number;
  test_case_id: number;
  status: string;
  start_time: string;
  end_time?: string;
  duration_ms: number;
  step_results: StepResult[];
  actual_result?: string;
  error_message?: string;
}

// 日志类型
export interface ExecutionLog {
  task_id: number;
  case_id?: number;
  case_no?: string;
  status: number;
  log: string;
  timestamp: string;
}

// 进度类型
export interface ExecutionProgress {
  task_id: number;
  progress: number;
  success_count: number;
  fail_count: number;
  current_case: number;
  total_cases: number;
  timestamp: string;
}

// 任务摘要类型
export interface TaskSummary {
  task_id: number;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  skipped_cases: number;
  total_duration_ms: number;
  pass_rate: number;
}

// 任务存储
export const useTaskStore = defineStore('task', {
  state: () => ({
    // 任务列表
    taskList: [] as TestTask[],
    // 任务详情
    taskDetail: null as TestTask | null,
    // 执行结果列表
    taskResults: [] as TestResult[],
    // 任务执行结果详情
    executionDetails: new Map<number, TaskExecutionResult>(),
    // 执行日志
    executionLogs: [] as ExecutionLog[],
    // 执行进度
    executionProgress: null as ExecutionProgress | null,
    // 任务摘要
    taskSummary: null as TaskSummary | null,
    // 加载状态
    loading: false,
    // 错误信息
    error: null as string | null
  }),

  getters: {
    // 任务状态文本
    taskStatusText(): (status: number) => string {
      return (status: number): string => {
        const statusMap: Record<number, string> = {
          [TaskStatus.WAITING]: '等待执行',
          [TaskStatus.RUNNING]: '执行中',
          [TaskStatus.COMPLETED]: '执行完成',
          [TaskStatus.FAILED]: '执行失败',
          [TaskStatus.STOPPED]: '已停止'
        };
        return statusMap[status] || '未知状态';
      };
    },

    // 任务状态颜色
    taskStatusColor(): (status: number) => string {
      return (status: number): string => {
        const colorMap: Record<number, string> = {
          [TaskStatus.WAITING]: 'info',    // 等待执行 - 灰色
          [TaskStatus.RUNNING]: 'primary',  // 执行中 - 蓝色
          [TaskStatus.COMPLETED]: 'success', // 执行完成 - 绿色
          [TaskStatus.FAILED]: 'danger',    // 执行失败 - 红色
          [TaskStatus.STOPPED]: 'warning'   // 已停止 - 橙色
        };
        return colorMap[status] || 'info';
      };
    },

    // 执行状态文本
    execStatusText(): (status: number) => string {
      return (status: number): string => {
        const statusMap: Record<number, string> = {
          [ExecutionStatus.PENDING]: '未执行',
          [ExecutionStatus.RUNNING]: '执行中',
          [ExecutionStatus.PASSED]: '执行成功',
          [ExecutionStatus.FAILED]: '执行失败',
          [ExecutionStatus.SKIPPED]: '已跳过',
          [ExecutionStatus.ERROR]: '执行错误'
        };
        return statusMap[status] || '未知状态';
      };
    },

    // 执行状态颜色
    execStatusColor(): (status: number) => string {
      return (status: number): string => {
        const colorMap: Record<number, string> = {
          [ExecutionStatus.PENDING]: 'info',    // 未执行 - 灰色
          [ExecutionStatus.RUNNING]: 'primary',  // 执行中 - 蓝色
          [ExecutionStatus.PASSED]: 'success',   // 通过 - 绿色
          [ExecutionStatus.FAILED]: 'danger',    // 失败 - 红色
          [ExecutionStatus.SKIPPED]: 'warning', // 跳过 - 橙色
          [ExecutionStatus.ERROR]: 'danger'     // 错误 - 红色
        };
        return colorMap[status] || 'info';
      };
    },

    // 日志状态文本
    logStatusText(): (status: number) => string {
      return (status: number): string => {
        const statusMap: Record<number, string> = {
          0: '信息',
          1: '成功',
          2: '错误',
          3: '警告'
        };
        return statusMap[status] || '未知';
      };
    },

    // 日志状态颜色
    logStatusColor(): (status: number) => string {
      return (status: number): string => {
        const colorMap: Record<number, string> = {
          0: 'info',
          1: 'success',
          2: 'danger',
          3: 'warning'
        };
        return colorMap[status] || 'info';
      };
    },

    // 任务通过率
    taskPassRate(): number {
      if (!this.taskDetail) return 0;
      const { total_count, success_count } = this.taskDetail;
      return total_count > 0 ? Math.round((success_count / total_count) * 100) : 0;
    },

    // 当前执行中的任务
    runningTasks(): TestTask[] {
      return this.taskList.filter(task => task.status === TaskStatus.RUNNING);
    }
  },

  actions: {
    // 获取任务列表
    async fetchTaskList(params?: {
      project_id?: number;
      status?: number | string;
      page?: number;
      page_size?: number;
    }) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.getTaskList(params || {});
        // 兼容不同的响应格式
        const data = response.data?.data || response.data;
        const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
        this.taskList = items;
        return {
          items: this.taskList,
          total: data?.total || this.taskList.length
        };
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 获取任务详情
    async fetchTaskDetail(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.getTaskDetail(taskId, projectId);
        const data = response.data?.data || response.data || {};
        this.taskDetail = data.task || data;
        return this.taskDetail;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 获取任务执行结果
    async fetchTaskResults(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.getTaskResults(taskId, projectId);
        const data = response.data?.data || response.data || {};
        this.taskResults = data.results || data.items || data || [];
        return this.taskResults;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 获取任务执行摘要
    async fetchTaskSummary(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.getTaskSummary(taskId, projectId);
        const data = response.data?.data || response.data || {};
        this.taskSummary = data;
        return this.taskSummary;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 创建任务
    async createTask(_data: {
      task_name: string;
      project_id: number;
      description?: string;
      case_ids: number[];
    }) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.createTask(_data);
        const taskData = response.data?.data || response.data || {};
        return taskData;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 开始执行任务
    async startTask(taskId: number, projectId?: number, executionMode?: 'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart', mobileDeviceId?: string) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.startTask(taskId, projectId, executionMode, mobileDeviceId);
        await this.fetchTaskDetail(taskId, projectId);
        return response.data;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 停止执行任务
    async stopTask(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.stopTask(taskId, projectId);
        await this.fetchTaskDetail(taskId, projectId);
        return response.data;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 执行任务（创建并立即执行）
    async runTask(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        const response = await testTaskApi.runTask(taskId, projectId);
        return response.data;
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 删除任务
    async deleteTask(taskId: number, projectId?: number) {
      this.loading = true;
      this.error = null;
      try {
        await testTaskApi.deleteTask(taskId, projectId);
        this.taskList = this.taskList.filter(task => task.id !== taskId);
      } catch (error: unknown) {
        this.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    // 清除执行日志
    clearExecutionLogs() {
      this.executionLogs = [];
    },

    // 添加执行日志
    addExecutionLog(log: ExecutionLog) {
      this.executionLogs.push(log);
      // 限制日志数量，防止内存溢出
      if (this.executionLogs.length > 1000) {
        this.executionLogs = this.executionLogs.slice(-500);
      }
    },

    // 更新执行进度
    updateExecutionProgress(progress: ExecutionProgress) {
      this.executionProgress = progress;
      // 同时更新任务列表中的进度
      const task = this.taskList.find(t => t.id === progress.task_id);
      if (task) {
        task.progress = progress.progress;
        task.success_count = progress.success_count;
        task.fail_count = progress.fail_count;
      }
      // 更新详情中的进度
      if (this.taskDetail?.id === progress.task_id) {
        this.taskDetail.progress = progress.progress;
        this.taskDetail.success_count = progress.success_count;
        this.taskDetail.fail_count = progress.fail_count;
      }
    },

    // 更新任务状态
    updateTaskStatus(taskId: number, status: number) {
      const task = this.taskList.find(t => t.id === taskId);
      if (task) {
        task.status = status;
      }
      if (this.taskDetail?.id === taskId) {
        this.taskDetail.status = status;
      }
    },

    // 重置状态
    resetState() {
      this.taskList = [];
      this.taskDetail = null;
      this.taskResults = [];
      this.executionDetails = new Map();
      this.executionLogs = [];
      this.executionProgress = null;
      this.taskSummary = null;
      this.loading = false;
      this.error = null;
    }
  }
});