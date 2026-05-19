import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { TableInstance } from 'element-plus'
import type { ExtractSharedState, ProjectItem, FileItem, ResourceRow, TestPointItem } from './types'

export function createSharedState(): ExtractSharedState {
  const router = useRouter()
  const route = useRoute()
  const currentStep = ref(0)
  const formData = reactive({ project_id: '' as number | '' })
  const projects = ref<ProjectItem[]>([])
  const files = ref<FileItem[]>([])
  const selectedResource = ref<ResourceRow | null>(null)
  const testPoints = ref<TestPointItem[]>([])
  const extracting = ref(false)
  const saving = ref(false)
  const batchDeleting = ref(false)
  const deleting = ref(false)
  const savedFromDb = ref(false)
  const loadingTestPoints = ref(false)
  const selectedRows = ref<TestPointItem[]>([])
  const testPointTable = ref<TableInstance>()
  const currentPage = ref(1)
  const pageSize = ref(10)
  const dbTotal = ref(0)
  const progress = ref(0)
  const progressText = ref('准备提取...')
  const progressInterval = ref<ReturnType<typeof setInterval> | null>(null)
  const errorMessage = ref('')
  const dialogVisible = ref(false)
  const resourceTypeFilter = ref('')
  const editForm = reactive<TestPointItem>({
    id: 0,
    module: '',
    function: '',
    point: '',
    priority: 2,
  })
  const editingIndex = ref(-1)
  const updating = ref(false)

  return {
    router,
    route,
    currentStep,
    formData,
    projects,
    files,
    selectedResource,
    testPoints,
    extracting,
    saving,
    batchDeleting,
    deleting,
    savedFromDb,
    loadingTestPoints,
    selectedRows,
    testPointTable,
    currentPage,
    pageSize,
    dbTotal,
    progress,
    progressText,
    progressInterval,
    errorMessage,
    dialogVisible,
    resourceTypeFilter,
    editForm,
    editingIndex,
    updating,
  }
}
