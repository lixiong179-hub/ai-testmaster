import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/store/task'
import { useProjectStore } from '@/store/project'

export function useTaskList() {
  const router = useRouter()
  const route = useRoute()
  const taskStore = useTaskStore()
  const projectStore = useProjectStore()

  const projectId = computed(() => Number(route.params.projectId) || 0)
  const loading = computed(() => taskStore.loading)
  const filter = ref({
    status: '' as string | number | undefined,
    projectId: undefined as number | undefined,
  })
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)
  const taskList = computed(() => taskStore.taskList)
  const projectList = computed(() => projectStore.projects || [])
  const isOverview = computed(() => !route.params.projectId)

  const taskStatusText = (status: number): string => taskStore.taskStatusText(status)
  const taskStatusColor = (status: number): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
    taskStore.taskStatusColor(status) as 'primary' | 'success' | 'warning' | 'info' | 'danger'

  const getProgressColor = (progress: number): string => {
    if (progress < 30) return '#409EFF'
    if (progress < 70) return '#E6A23C'
    return '#67C23A'
  }

  const getProgressStatus = (task: {
    status: number
    fail_count: number
  }): 'exception' | 'success' | undefined => {
    if (task.status === 3) return 'exception'
    if (task.status === 2 && task.fail_count === 0) return 'success'
    return undefined
  }

  const handleSizeChange = (size: number) => {
    pageSize.value = size
    fetchTaskList()
  }
  const handleCurrentChange = (current: number) => {
    page.value = current
    fetchTaskList()
  }

  const effectiveProjectId = computed(() => {
    if (projectId.value) return projectId.value
    return filter.value.projectId || 0
  })

  const fetchTaskList = async () => {
    try {
      const params: {
        page: number
        page_size: number
        project_id?: number
        task_status?: number | string
      } = { page: page.value, page_size: pageSize.value }
      if (effectiveProjectId.value) params.project_id = effectiveProjectId.value
      if (filter.value.status !== undefined && filter.value.status !== '')
        params.task_status = filter.value.status
      const result = await taskStore.fetchTaskList(params)
      const items = Array.isArray(result?.items) ? result.items : []
      if (items.length !== taskStore.taskList.length) taskStore.taskList = items
      total.value = result?.total || 0
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取任务列表失败'
      ElMessage.error(msg)
    }
  }

  const fetchProjects = async () => {
    if (projectList.value.length === 0) {
      try {
        await projectStore.fetchProjects()
      } catch {
        /* project list fetch failure is non-blocking */
      }
    }
  }

  const createTask = () => {
    const pid = effectiveProjectId.value
    if (!pid) {
      ElMessage.warning('请先选择项目')
      return
    }
    router.push(`/home/task/create/${pid}`)
  }

  const goToTestPointManagement = () => {
    const pid = effectiveProjectId.value
    router.push({
      path: '/home/case/test-point-management',
      query: pid ? { projectId: String(pid) } : {},
    })
  }

  const viewTask = (task: { id: number }) => {
    router.push(`/home/task/detail/${task.id}?project_id=${effectiveProjectId.value}`)
  }
  const handleRowClick = (row: { id: number }) => {
    viewTask(row)
  }

  const startTask = async (task: { id: number }) => {
    try {
      await ElMessageBox.confirm('确定要启动此任务吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await taskStore.startTask(task.id, effectiveProjectId.value)
      ElMessage.success('任务已开始执行')
      fetchTaskList()
    } catch (error: unknown) {
      if (error !== 'cancel') {
        const msg = error instanceof Error ? error.message : '启动任务失败'
        ElMessage.error(msg)
      }
    }
  }

  const stopTask = async (task: { id: number }) => {
    try {
      await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await taskStore.stopTask(task.id, effectiveProjectId.value)
      ElMessage.success('任务已停止')
      fetchTaskList()
    } catch (error: unknown) {
      if (error !== 'cancel') {
        const msg = error instanceof Error ? error.message : '停止任务失败'
        ElMessage.error(msg)
      }
    }
  }

  const deleteTaskConfirm = async (task: { id: number; task_name: string }) => {
    try {
      await ElMessageBox.confirm(
        `确定要删除任务"${task.task_name}"吗？此操作不可恢复。`,
        '删除确认',
        { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
      )
      await taskStore.deleteTask(task.id, effectiveProjectId.value)
      ElMessage.success('任务删除成功')
      fetchTaskList()
    } catch (error: unknown) {
      if (error !== 'cancel') {
        const msg = error instanceof Error ? error.message : '删除任务失败'
        ElMessage.error(msg)
      }
    }
  }

  onMounted(() => {
    fetchProjects()
    fetchTaskList()
  })

  return {
    projectId,
    loading,
    filter,
    page,
    pageSize,
    total,
    taskList,
    projectList,
    isOverview,
    taskStatusText,
    taskStatusColor,
    getProgressColor,
    getProgressStatus,
    handleSizeChange,
    handleCurrentChange,
    fetchTaskList,
    createTask,
    goToTestPointManagement,
    viewTask,
    handleRowClick,
    startTask,
    stopTask,
    deleteTaskConfirm,
  }
}
