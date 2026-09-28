import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import selfHealingApi from '@/api/selfHealing'
import type { SelfHealingAudit, AuditListParams } from '@/api/selfHealing'
import { failureTypeOptions, strategyOptions } from '@/api/selfHealing'
import { ProjectAPI } from '@/api/project'
import type { Project } from '@/api/project'

// 重新导出选项常量，便于页面组件直接引用
export { failureTypeOptions, strategyOptions }

/**
 * 自愈审计列表 composable。
 *
 * 说明：后端 list_audits 端点仅支持 project_id/test_case_id/page/page_size 过滤，
 * 故 failure_type / confidence / dateRange 在前端对当前页真实数据做客户端过滤
 * （基于真实后端数据，非 Mock）。project_id 与分页走服务端。
 */
export function useAuditList() {
  const loading = ref(false)
  const rollingBack = ref(false)
  const audits = ref<SelfHealingAudit[]>([])
  const projects = ref<Project[]>([])

  // 详情弹窗状态
  const detailVisible = ref(false)
  const currentAudit = ref<SelfHealingAudit | null>(null)

  const pagination = reactive({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  const filters = reactive({
    projectId: undefined as number | undefined,
    failureType: '' as string,
    confidenceMin: undefined as number | undefined,
    confidenceMax: undefined as number | undefined,
    dateRange: null as [string, string] | null,
  })

  /** 当前选中项目名称（用于表格"项目"列展示，审计记录本身仅含 test_case_id） */
  const currentProjectName = computed<string>(() => {
    if (!filters.projectId) return '-'
    const p = projects.value.find((item) => item.id === filters.projectId)
    return p?.name ?? `项目#${filters.projectId}`
  })

  /**
   * 客户端过滤当前页数据：failure_type / confidence 区间 / 日期范围。
   * 后端不支持这三个过滤条件，故在前端对真实分页数据二次过滤。
   */
  const filteredAudits = computed<SelfHealingAudit[]>(() => {
    return audits.value.filter((item) => {
      if (filters.failureType && item.failure_type !== filters.failureType) {
        return false
      }
      if (item.confidence != null) {
        if (filters.confidenceMin != null && item.confidence < filters.confidenceMin) {
          return false
        }
        if (filters.confidenceMax != null && item.confidence > filters.confidenceMax) {
          return false
        }
      } else if (filters.confidenceMin != null || filters.confidenceMax != null) {
        // 置信度为空且用户指定了区间，视为不匹配
        return false
      }
      if (filters.dateRange && filters.dateRange.length === 2) {
        const createdAt = new Date(item.created_at).getTime()
        const start = new Date(filters.dateRange[0]).getTime()
        const end = new Date(filters.dateRange[1]).getTime()
        if (Number.isNaN(createdAt) || createdAt < start || createdAt > end) {
          return false
        }
      }
      return true
    })
  })

  /** 加载项目下拉数据 */
  const loadProjects = async (): Promise<void> => {
    try {
      const res = await ProjectAPI.getProjectList({ page: 1, page_size: 100 })
      projects.value = res?.data?.items ?? []
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取项目列表失败'
      ElMessage.error(msg)
    }
  }

  /** 加载审计列表（服务端仅过滤 project_id 与分页） */
  const loadAudits = async (): Promise<void> => {
    loading.value = true
    try {
      const params: AuditListParams = {
        page: pagination.page,
        page_size: pagination.pageSize,
      }
      if (filters.projectId) {
        params.project_id = filters.projectId
      }
      const res = await selfHealingApi.getAudits(params)
      const data = res?.data
      audits.value = data?.items ?? []
      pagination.total = data?.total ?? 0
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取自愈审计列表失败'
      ElMessage.error(msg)
      audits.value = []
      pagination.total = 0
    } finally {
      loading.value = false
    }
  }

  /** 搜索：重置页码后加载 */
  const handleSearch = (): void => {
    pagination.page = 1
    loadAudits()
  }

  /** 重置筛选条件 */
  const handleReset = (): void => {
    filters.projectId = undefined
    filters.failureType = ''
    filters.confidenceMin = undefined
    filters.confidenceMax = undefined
    filters.dateRange = null
    pagination.page = 1
    loadAudits()
  }

  /** 分页大小变更 */
  const handleSizeChange = (size: number): void => {
    pagination.pageSize = size
    pagination.page = 1
    loadAudits()
  }

  /** 当前页变更 */
  const handleCurrentChange = (page: number): void => {
    pagination.page = page
    loadAudits()
  }

  /** 打开详情弹窗 */
  const openDetail = (row: SelfHealingAudit): void => {
    currentAudit.value = row
    detailVisible.value = true
  }

  /** 关闭详情弹窗 */
  const closeDetail = (): void => {
    detailVisible.value = false
    currentAudit.value = null
  }

  /** 回滚自愈变更（二次确认） */
  const handleRollback = (row: SelfHealingAudit): void => {
    ElMessageBox.confirm(
      `确定回滚审计 #${row.id} 的自愈变更吗？将恢复旧选择器并写入回滚审计。`,
      '回滚确认',
      {
        confirmButtonText: '确定回滚',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
      .then(async () => {
        rollingBack.value = true
        try {
          const res = await selfHealingApi.rollbackAudit(row.id)
          if (res.code === 200) {
            ElMessage.success(res.data?.message || '回滚成功')
            await loadAudits()
          } else {
            ElMessage.error(res.message || '回滚失败')
          }
        } catch (error: unknown) {
          const msg = error instanceof Error ? error.message : '回滚失败'
          ElMessage.error(msg)
        } finally {
          rollingBack.value = false
        }
      })
      .catch(() => {
        // 用户取消，无需提示
      })
  }

  onMounted(() => {
    loadProjects()
    loadAudits()
  })

  return {
    loading,
    rollingBack,
    audits,
    filteredAudits,
    projects,
    currentProjectName,
    detailVisible,
    currentAudit,
    pagination,
    filters,
    loadAudits,
    handleSearch,
    handleReset,
    handleSizeChange,
    handleCurrentChange,
    openDetail,
    closeDetail,
    handleRollback,
  }
}
