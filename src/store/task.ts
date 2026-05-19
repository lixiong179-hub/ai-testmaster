import { defineStore } from 'pinia'
import testTaskApi from '../api/testTask'
import { TaskStatus, ExecutionStatus } from '../api/testTask'
import type { TestTask, TestResult, TaskExecutionResult, ExecutionLog, ExecutionProgress, TaskSummary } from './taskTypes'
import { extractTaskResponseData } from './taskTypes'

export { TaskStatus, ExecutionStatus } from '../api/testTask'
export type { TestTask, TestResult, TaskExecutionResult, ExecutionLog, ExecutionProgress, TaskSummary } from './taskTypes'

export const useTaskStore = defineStore('task', {
  state: () => ({
    taskList: [] as TestTask[],
    taskDetail: null as TestTask | null,
    taskResults: [] as TestResult[],
    executionDetails: new Map<number, TaskExecutionResult>(),
    executionLogs: [] as ExecutionLog[],
    executionProgress: null as ExecutionProgress | null,
    taskSummary: null as TaskSummary | null,
    loading: false,
    error: null as string | null,
  }),

  getters: {
    taskStatusText(): (status: number) => string {
      return (status: number): string => {
        const statusMap: Record<number, string> = {
          [TaskStatus.WAITING]: '等待执行', [TaskStatus.RUNNING]: '执行中',
          [TaskStatus.COMPLETED]: '执行完成', [TaskStatus.FAILED]: '执行失败', [TaskStatus.STOPPED]: '已停止',
        }
        return statusMap[status] || '未知状态'
      }
    },
    taskStatusColor(): (status: number) => string {
      return (status: number): string => {
        const colorMap: Record<number, string> = {
          [TaskStatus.WAITING]: 'info', [TaskStatus.RUNNING]: 'primary',
          [TaskStatus.COMPLETED]: 'success', [TaskStatus.FAILED]: 'danger', [TaskStatus.STOPPED]: 'warning',
        }
        return colorMap[status] || 'info'
      }
    },
    execStatusText(): (status: number) => string {
      return (status: number): string => {
        const statusMap: Record<number, string> = {
          [ExecutionStatus.PENDING]: '未执行', [ExecutionStatus.PASSED]: '执行成功',
          [ExecutionStatus.FAILED]: '执行失败', [ExecutionStatus.BLOCKED]: '阻塞',
        }
        return statusMap[status] || '未知状态'
      }
    },
    execStatusColor(): (status: number) => string {
      return (status: number): string => {
        const colorMap: Record<number, string> = {
          [ExecutionStatus.PENDING]: 'info', [ExecutionStatus.PASSED]: 'success',
          [ExecutionStatus.FAILED]: 'danger', [ExecutionStatus.BLOCKED]: 'warning',
        }
        return colorMap[status] || 'info'
      }
    },
    logStatusText(): (status: number) => string {
      return (status: number): string => { const m: Record<number, string> = { 0: '信息', 1: '成功', 2: '错误', 3: '警告' }; return m[status] || '未知' }
    },
    logStatusColor(): (status: number) => string {
      return (status: number): string => { const m: Record<number, string> = { 0: 'info', 1: 'success', 2: 'danger', 3: 'warning' }; return m[status] || 'info' }
    },
    taskPassRate(): number {
      if (!this.taskDetail) return 0
      const { total_count, success_count } = this.taskDetail
      return total_count > 0 ? Math.round((success_count / total_count) * 100) : 0
    },
    runningTasks(): TestTask[] { return this.taskList.filter((task) => task.status === TaskStatus.RUNNING) },
  },

  actions: {
    async fetchTaskList(params?: { project_id?: number; task_status?: number | string; page?: number; page_size?: number }) {
      this.loading = true; this.error = null
      try {
        const response = await testTaskApi.getTaskList(params || {})
        const data = extractTaskResponseData<{ items?: TestTask[]; total?: number }>(response)
        const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : []
        this.taskList = items; return { items: this.taskList, total: data?.total || this.taskList.length }
      } catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async fetchTaskDetail(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.getTaskDetail(taskId, projectId); const data = extractTaskResponseData<any>(response); this.taskDetail = data.task || data; return this.taskDetail }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async fetchTaskResults(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.getTaskResults(taskId, projectId); const data = extractTaskResponseData<any>(response); this.taskResults = data.results || data.items || data || []; return this.taskResults }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async fetchTaskSummary(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.getTaskSummary(taskId, projectId); const data = extractTaskResponseData<any>(response); this.taskSummary = data; return this.taskSummary }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async createTask(_data: { task_name: string; project_id: number; description?: string; case_ids: number[] }) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.createTask(_data); return extractTaskResponseData<any>(response) }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async startTask(taskId: number, projectId?: number, executionMode?: 'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart', mobileDeviceId?: string) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.startTask(taskId, projectId, executionMode, mobileDeviceId); await this.fetchTaskDetail(taskId, projectId); return extractTaskResponseData<any>(response) }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async stopTask(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.stopTask(taskId, projectId); await this.fetchTaskDetail(taskId, projectId); return extractTaskResponseData<any>(response) }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async runTask(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { const response = await testTaskApi.runTask(taskId, projectId); return extractTaskResponseData<any>(response) }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    async deleteTask(taskId: number, projectId?: number) {
      this.loading = true; this.error = null
      try { await testTaskApi.deleteTask(taskId, projectId); this.taskList = this.taskList.filter((task) => task.id !== taskId) }
      catch (error: unknown) { this.error = error instanceof Error ? error.message : String(error); throw error }
      finally { this.loading = false }
    },
    clearExecutionLogs() { this.executionLogs = [] },
    addExecutionLog(log: ExecutionLog) { this.executionLogs.push(log); if (this.executionLogs.length > 1000) this.executionLogs = this.executionLogs.slice(-500) },
    updateExecutionProgress(progress: ExecutionProgress) {
      this.executionProgress = progress
      const task = this.taskList.find((t) => t.id === progress.task_id)
      if (task) { task.progress = progress.progress; task.success_count = progress.success_count; task.fail_count = progress.fail_count }
      if (this.taskDetail?.id === progress.task_id) { this.taskDetail.progress = progress.progress; this.taskDetail.success_count = progress.success_count; this.taskDetail.fail_count = progress.fail_count }
    },
    updateTaskStatus(taskId: number, status: number) {
      const task = this.taskList.find((t) => t.id === taskId); if (task) task.status = status
      if (this.taskDetail?.id === taskId) this.taskDetail.status = status
    },
    resetState() {
      this.taskList = []; this.taskDetail = null; this.taskResults = []; this.executionDetails = new Map()
      this.executionLogs = []; this.executionProgress = null; this.taskSummary = null; this.loading = false; this.error = null
    },
  },
})
