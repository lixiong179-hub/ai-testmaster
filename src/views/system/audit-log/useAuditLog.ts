import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import auditLogApi from '@/api/auditLog'
import type { AuditLogItem, AuditLogQueryParams } from '@/api/auditLog'

/** 目标类型选项 */
export const targetKindOptions = [
  { label: '项目', value: 'project' },
  { label: '迭代', value: 'iteration' },
  { label: '流水线', value: 'pipeline' },
  { label: '测试用例', value: 'test_case' },
  { label: '测试点', value: 'test_point' },
  { label: '测试任务', value: 'test_task' },
] as const

/** 操作类型选项 */
export const actionOptions = [
  { label: '创建', value: 'create' },
  { label: '更新', value: 'update' },
  { label: '删除', value: 'delete' },
  { label: '执行', value: 'execute' },
  { label: '审批', value: 'approve' },
  { label: '拒绝', value: 'reject' },
] as const

export function useAuditLog() {
  const loading = ref(false)
  const logs = ref<AuditLogItem[]>([])

  /** 分页状态 */
  const pagination = reactive({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  /** 筛选条件 */
  const filters = reactive({
    action: '' as string,
    actorId: '' as string,
    targetKind: '' as string,
    dateRange: null as [string, string] | null,
  })

  /** 加载审计日志数据 */
  const loadLogs = async (): Promise<void> => {
    loading.value = true
    try {
      const params: AuditLogQueryParams = {
        page: pagination.page,
        page_size: pagination.pageSize,
      }
      if (filters.action) {
        params.action = filters.action
      }
      if (filters.actorId) {
        const parsed = Number(filters.actorId)
        if (!Number.isNaN(parsed) && parsed > 0) {
          params.actor_id = parsed
        }
      }
      if (filters.targetKind) {
        params.target_kind = filters.targetKind
      }
      if (filters.dateRange && filters.dateRange.length === 2) {
        params.since = filters.dateRange[0]
        params.until = filters.dateRange[1]
      }

      const response = await auditLogApi.getLogs(params)
      const data = response.data as unknown as { items: AuditLogItem[]; total: number }
      logs.value = data.items ?? []
      pagination.total = data.total ?? 0
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取审计日志失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  /** 搜索 */
  const handleSearch = (): void => {
    pagination.page = 1
    loadLogs()
  }

  /** 重置筛选 */
  const handleReset = (): void => {
    filters.action = ''
    filters.actorId = ''
    filters.targetKind = ''
    filters.dateRange = null
    pagination.page = 1
    loadLogs()
  }

  /** 分页大小变更 */
  const handleSizeChange = (size: number): void => {
    pagination.pageSize = size
    pagination.page = 1
    loadLogs()
  }

  /** 当前页变更 */
  const handleCurrentChange = (page: number): void => {
    pagination.page = page
    loadLogs()
  }

  onMounted(() => {
    loadLogs()
  })

  return {
    loading,
    logs,
    pagination,
    filters,
    loadLogs,
    handleSearch,
    handleReset,
    handleSizeChange,
    handleCurrentChange,
  }
}
