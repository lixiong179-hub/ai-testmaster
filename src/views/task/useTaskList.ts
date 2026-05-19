import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/store/task'

export function useTaskList() {
  const router = useRouter()
  const route = useRoute()
  const taskStore = useTaskStore()

  const projectId = computed(() => Number(route.params.projectId) || 0)
  const loading = computed(() => taskStore.loading)
  const filter = ref({ status: '' as string | number | undefined })
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)
  const taskList = computed(() => taskStore.taskList)

  const taskStatusText = (status: number): string => taskStore.taskStatusText(status)
  const taskStatusColor = (status: number): string => taskStore.taskStatusColor(status)

  const getProgressColor = (progress: number): string => {
    if (progress < 30) return '#409EFF'
    if (progress < 70) return '#E6A23C'
    return '#67C23A'
  }

  const getProgressStatus = (task: any): string | undefined => {
    if (task.status === 3) return 'exception'
    if (task.status === 2 && task.fail_count === 0) return 'success'
    return undefined
  }

  const handleSizeChange = (size: number) => { pageSize.value = size; fetchTaskList() }
  const handleCurrentChange = (current: number) => { page.value = current; fetchTaskList() }

  const fetchTaskList = async () => {
    try {
      const params: any = { page: page.value, page_size: pageSize.value }
      if (projectId.value) params.project_id = projectId.value
      if (filter.value.status !== undefined && filter.value.status !== '') params.task_status = filter.value.status
      const result = await taskStore.fetchTaskList(params)
      const items = Array.isArray(result?.items) ? result.items : []
      if (items.length !== taskStore.taskList.length) taskStore.taskList = items
      total.value = result?.total || 0
    } catch (error: any) { ElMessage.error(error.message || '获取任务列表失败') }
  }

  const createTask = () => { router.push(`/home/task/create/${projectId.value}`) }

  const goToTestPointManagement = () => {
    router.push({ path: '/home/case/test-point-management', query: { projectId: String(projectId.value) } })
  }

  const viewTask = (task: any) => { router.push(`/home/task/detail/${task.id}?project_id=${projectId.value}`) }
  const handleRowClick = (row: any) => { viewTask(row) }

  const startTask = async (task: any) => {
    try {
      await ElMessageBox.confirm('确定要启动此任务吗？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
      await taskStore.startTask(task.id, projectId.value); ElMessage.success('任务已开始执行'); fetchTaskList()
    } catch (error: any) { if (error !== 'cancel') ElMessage.error(error.message || '启动任务失败') }
  }

  const stopTask = async (task: any) => {
    try {
      await ElMessageBox.confirm('确定要停止此任务吗？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
      await taskStore.stopTask(task.id, projectId.value); ElMessage.success('任务已停止'); fetchTaskList()
    } catch (error: any) { if (error !== 'cancel') ElMessage.error(error.message || '停止任务失败') }
  }

  const deleteTaskConfirm = async (task: any) => {
    try {
      await ElMessageBox.confirm(`确定要删除任务"${task.task_name}"吗？此操作不可恢复。`, '删除确认', { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' })
      await taskStore.deleteTask(task.id, projectId.value); ElMessage.success('任务删除成功'); fetchTaskList()
    } catch (error: any) { if (error !== 'cancel') ElMessage.error(error.message || '删除任务失败') }
  }

  onMounted(() => { fetchTaskList() })

  return {
    projectId, loading, filter, page, pageSize, total, taskList,
    taskStatusText, taskStatusColor, getProgressColor, getProgressStatus,
    handleSizeChange, handleCurrentChange, fetchTaskList, createTask,
    goToTestPointManagement, viewTask, handleRowClick, startTask, stopTask, deleteTaskConfirm,
  }
}
