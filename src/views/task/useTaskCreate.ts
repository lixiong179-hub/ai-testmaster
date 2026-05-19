import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/store/task'
import testTaskApi from '@/api/testTask'

export function useTaskCreate() {
  const router = useRouter()
  const route = useRoute()
  const taskStore = useTaskStore()
  const formRef = ref()
  const tableRef = ref()
  const loading = ref(false)
  const submitting = ref(false)

  const projectId = computed(() => Number(route.params.projectId) || 0)

  const form = ref({
    task_name: '',
    description: '',
    project_id: '' as number | '',
    case_ids: [] as number[],
  })

  watch(projectId, (newVal) => { form.value.project_id = newVal }, { immediate: true })

  const filter = ref({ module: '', priority: '' as number | '', keyword: '' })
  const cases = ref<any[]>([])
  const page = ref(1)
  const pageSize = ref(50)
  const total = ref(0)

  const modules = computed(() => {
    const moduleSet = new Set<string>()
    cases.value.forEach((item) => { if (item.module) moduleSet.add(item.module) })
    return Array.from(moduleSet)
  })

  const filteredCases = computed(() => {
    return cases.value.filter((item) => {
      let match = true
      if (filter.value.module) match = match && item.module === filter.value.module
      if (filter.value.priority !== '') match = match && item.priority === filter.value.priority
      if (filter.value.keyword) {
        const keyword = filter.value.keyword.toLowerCase()
        match = match && ((item.title && item.title.toLowerCase().includes(keyword)) || (item.case_no && item.case_no.toLowerCase().includes(keyword)))
      }
      return match
    })
  })

  const selectAll = computed({
    get: () => {
      if (filteredCases.value.length === 0) return false
      return filteredCases.value.every((item) => form.value.case_ids.includes(item.id))
    },
    set: (value) => {
      if (value) {
        const ids = filteredCases.value.map((item) => item.id)
        form.value.case_ids = [...new Set([...form.value.case_ids, ...ids])]
      } else {
        const idsToRemove = filteredCases.value.map((item) => item.id)
        form.value.case_ids = form.value.case_ids.filter((id) => !idsToRemove.includes(id))
      }
    },
  })

  const rules = {
    task_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }, { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }],
    case_ids: [{ required: true, validator: (_rule: any, value: any, callback: any) => { value.length === 0 ? callback(new Error('请至少选择一条用例')) : callback() }, trigger: 'change' }],
  }

  const priorityText = (priority: number | undefined): string => {
    const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
    return priority ? map[priority] || '未知' : '-'
  }

  const priorityType = (priority: number | undefined): string => {
    const map: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'success' }
    return priority ? map[priority] || 'info' : 'info'
  }

  const handleSelectionChange = (selection: any[]) => { form.value.case_ids = selection.map((item) => item.id) }
  const handleSelectAll = (value: boolean) => { value ? tableRef.value?.toggleAllSelection() : tableRef.value?.clearSelection() }
  const clearSelection = () => { tableRef.value?.clearSelection(); form.value.case_ids = [] }
  const handleSearch = () => { page.value = 1 }
  const handlePageChange = (newPage: number) => { page.value = newPage }

  const submitForm = async () => {
    if (!formRef.value) return
    await formRef.value.validate(async (valid: boolean) => {
      if (valid) {
        submitting.value = true
        try {
          await taskStore.createTask({
            task_name: form.value.task_name,
            project_id: form.value.project_id as number,
            description: form.value.description,
            case_ids: form.value.case_ids,
          })
          ElMessage.success('任务创建成功')
          router.push(`/home/task/list/${projectId.value}`)
        } catch (error: any) {
          ElMessage.error(error.message || '任务创建失败')
        } finally {
          submitting.value = false
        }
      }
    })
  }

  const resetForm = () => {
    if (formRef.value) {
      formRef.value.resetFields()
      form.value.description = ''
      form.value.case_ids = []
      tableRef.value?.clearSelection()
    }
  }

  const fetchAllProjectCases = async (targetProjectId: number) => {
    const pageSize = 100
    const allCases: any[] = []
    let currentPage = 1
    let totalPages = 1
    while (currentPage <= totalPages) {
      const response = (await testTaskApi.getProjectCases(targetProjectId, { page: currentPage, page_size: pageSize })) as any
      const payload = response?.data || response || {}
      const pageData = payload.items ? payload : payload.data || {}
      const items = Array.isArray(pageData.items) ? pageData.items : []
      const totalCount = Number(pageData.total || items.length || 0)
      allCases.push(...items)
      totalPages = Math.max(1, Math.ceil(totalCount / pageSize))
      if (items.length === 0) break
      currentPage += 1
    }
    const uniqueCases = new Map<number, any>()
    allCases.forEach((item) => { if (item?.id) uniqueCases.set(item.id, item) })
    return Array.from(uniqueCases.values())
  }

  const fetchProjectCases = async () => {
    loading.value = true
    try {
      cases.value = await fetchAllProjectCases(projectId.value)
      total.value = cases.value.length
      if (cases.value.length === 0) ElMessage.warning('该项目下暂无测试用例，请先生成测试用例')
    } catch (error: any) {
      ElMessage.error(error.message || '获取用例列表失败')
    } finally {
      loading.value = false
    }
  }

  onMounted(() => { fetchProjectCases() })

  return {
    formRef, tableRef, loading, submitting, projectId, form, filter, cases,
    page, pageSize, total, modules, filteredCases, selectAll, rules,
    priorityText, priorityType, handleSelectionChange, handleSelectAll,
    clearSelection, handleSearch, handlePageChange, submitForm, resetForm,
  }
}
