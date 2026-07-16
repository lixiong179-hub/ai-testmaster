import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, type FormInstance } from 'element-plus'
import type { TagType } from '@/types/element-plus'
import { useProjectStore } from '@/store/project'

export function useProjectList() {
  const router = useRouter()
  const projectStore = useProjectStore()

  const dialogVisible = ref(false)
  const projectFormRef = ref<FormInstance | null>(null)
  const searchKeyword = ref('')
  // 来源筛选：'' 全部 | manual 手动创建 | url_quick_test 快速测试
  // 后端暂未在 list 接口支持 source 过滤参数，故仅在前端客户端过滤
  const sourceFilter = ref<'' | 'manual' | 'url_quick_test'>('')

  const projectForm = ref({
    name: '',
    description: '',
    project_type: 'web' as 'web' | 'app',
    web_env_configs: {
      test: { url: '', username: '', password: '' },
      staging: { url: '', username: '', password: '' },
      prod: { url: '', username: '', password: '' },
    },
  })

  const projectRules = {
    name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
    project_type: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
  }

  // 来源枚举值标准化：缺失或非 url_quick_test 一律按 manual 兜底
  const resolveSource = (source?: string): 'manual' | 'url_quick_test' => {
    return source === 'url_quick_test' ? 'url_quick_test' : 'manual'
  }

  const filteredProjects = computed(() => {
    let list = projectStore.projects
    if (searchKeyword.value) {
      const kw = searchKeyword.value.toLowerCase()
      list = list.filter((p) => p.name.toLowerCase().includes(kw))
    }
    if (sourceFilter.value) {
      list = list.filter((p) => resolveSource(p.source) === sourceFilter.value)
    }
    return list
  })

  // 来源映射：用于表格 el-tag 的颜色与文本展示
  const getSourceTagType = (source?: string): TagType => {
    return source === 'url_quick_test' ? 'primary' : 'info'
  }
  const getSourceText = (source?: string): string => {
    return source === 'url_quick_test' ? '快速测试' : '手动创建'
  }

  const getStatusType = (status: number): TagType => {
    const m: Record<number, TagType> = { 0: 'info', 1: 'success', 2: 'warning' }
    return m[status] || 'info'
  }

  const getStatusText = (status: number) => {
    const m: Record<number, string> = { 0: '未激活', 1: '正常', 2: '归档' }
    return m[status] || '未知'
  }

  const handleSearch = () => {
    projectStore.fetchProjects()
  }

  const handleCurrentChange = (current: number) => {
    projectStore.currentPage = current
    projectStore.fetchProjects()
  }

  const handleSizeChange = (size: number) => {
    projectStore.pageSize = size
    projectStore.currentPage = 1
    projectStore.fetchProjects()
  }

  const openCreateDialog = () => {
    projectForm.value = {
      name: '',
      description: '',
      project_type: 'web' as 'web' | 'app',
      web_env_configs: {
        test: { url: '', username: '', password: '' },
        staging: { url: '', username: '', password: '' },
        prod: { url: '', username: '', password: '' },
      },
    }
    dialogVisible.value = true
  }

  const createProject = async () => {
    if (!projectFormRef.value) return
    await projectFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        const projectId = await projectStore.createProject({
          name: projectForm.value.name,
          description: projectForm.value.description,
          project_type: projectForm.value.project_type,
          web_env_configs:
            projectForm.value.project_type === 'web'
              ? projectForm.value.web_env_configs
              : undefined,
        })
        if (projectId) {
          dialogVisible.value = false
          goToDetail(projectId)
        }
      }
    })
  }

  const goToDetail = (projectId: number) => {
    router.push(`/home/project/detail?id=${projectId}`)
  }
  const goToTaskList = (projectId: number) => {
    router.push(`/home/task/list/${projectId}`)
  }
  const goToTestPointManagement = (projectId: number) => {
    router.push({
      path: '/home/case/test-point-management',
      query: { projectId: String(projectId) },
    })
  }

  const confirmDelete = (projectId: number) => {
    ElMessageBox.confirm('确定要删除此项目吗？删除后将级联删除关联的文件、测试点和用例。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(async () => {
        await projectStore.deleteProject(projectId)
      })
      .catch(() => {})
  }

  onMounted(() => {
    projectStore.fetchProjects()
  })

  return {
    projectStore,
    dialogVisible,
    projectFormRef,
    searchKeyword,
    sourceFilter,
    projectForm,
    projectRules,
    filteredProjects,
    getSourceTagType,
    getSourceText,
    getStatusType,
    getStatusText,
    handleSearch,
    handleCurrentChange,
    handleSizeChange,
    openCreateDialog,
    createProject,
    goToDetail,
    goToTaskList,
    goToTestPointManagement,
    confirmDelete,
  }
}
