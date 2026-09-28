import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  promptTemplateApi,
  type PromptTemplate,
  type PromptRegistry,
  type PromptTemplateCreate,
} from '@/api/promptTemplate'

/** 注册表单数据 */
interface RegisterFormData {
  prompt_key: string
  content: string
  description: string
}

/** 内容预览截断阈值（超出则支持折叠/展开） */
const PREVIEW_MAX_CHARS = 200

/** 单次拉取的最大版本数，覆盖常规 key 的全部版本 */
const FETCH_PAGE_SIZE = 100

export function usePromptTemplate() {
  const loading = ref(false)
  const actionLoading = ref(false)
  const registries = ref<PromptRegistry[]>([])
  const selectedKey = ref<string | null>(null)
  const filterText = ref('')
  /** 记录展开完整内容的版本 id 集合 */
  const expandedIds = ref<Set<number>>(new Set())

  // 注册新版本对话框
  const registerDialogVisible = ref(false)
  const registerFormRef = ref<FormInstance | null>(null)
  const registerForm = reactive<RegisterFormData>({
    prompt_key: '',
    content: '',
    description: '',
  })
  const registerRules = {
    prompt_key: [
      { required: true, message: '请输入 Prompt Key', trigger: 'blur' },
      { min: 1, max: 80, message: 'Key长度1-80位', trigger: 'blur' },
    ],
    content: [{ required: true, message: '请输入 Prompt 内容', trigger: 'blur' }],
  }

  /** 按关键字过滤后的注册表（左侧列表展示用） */
  const filteredRegistries = computed<PromptRegistry[]>(() => {
    const keyword = filterText.value.trim().toLowerCase()
    if (!keyword) return registries.value
    return registries.value.filter((r) => r.key.toLowerCase().includes(keyword))
  })

  /** 当前选中 key 对应的注册表项 */
  const currentRegistry = computed<PromptRegistry | null>(() => {
    if (!selectedKey.value) return null
    return registries.value.find((r) => r.key === selectedKey.value) ?? null
  })

  /** 当前选中 key 的版本列表（按版本号降序，最新在前） */
  const currentVersions = computed<PromptTemplate[]>(() => {
    if (!currentRegistry.value) return []
    return [...currentRegistry.value.versions].sort(
      (a, b) => b.prompt_version - a.prompt_version
    )
  })

  /** 将扁平列表按 prompt_key 分组为注册表 */
  const groupByKeys = (items: PromptTemplate[]): PromptRegistry[] => {
    const map = new Map<string, PromptTemplate[]>()
    for (const item of items) {
      const list = map.get(item.prompt_key) ?? []
      list.push(item)
      map.set(item.prompt_key, list)
    }
    const result: PromptRegistry[] = []
    for (const [key, versions] of map.entries()) {
      const sorted = versions.sort((a, b) => a.prompt_version - b.prompt_version)
      result.push({
        key,
        versions: sorted,
        defaultVersion: sorted.find((v) => v.is_default) ?? null,
        latestVersion: sorted[sorted.length - 1] ?? null,
      })
    }
    return result.sort((a, b) => a.key.localeCompare(b.key))
  }

  /** 加载全部 Prompt 模板并按 key 分组 */
  const loadAll = async (): Promise<void> => {
    loading.value = true
    try {
      const response = await promptTemplateApi.getList({
        page: 1,
        page_size: FETCH_PAGE_SIZE,
      })
      const items = response.data?.items ?? []
      registries.value = groupByKeys(items)
      // 保持当前选中或回退到首个 key
      if (registries.value.length > 0) {
        const exists = registries.value.some((r) => r.key === selectedKey.value)
        if (!exists) selectedKey.value = registries.value[0].key
      } else {
        selectedKey.value = null
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取 Prompt 模板列表失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  /** 选中某个 Prompt Key */
  const selectKey = (key: string): void => {
    selectedKey.value = key
    expandedIds.value = new Set()
  }

  /** 切换某版本内容预览的展开/折叠状态 */
  const toggleExpand = (id: number): void => {
    const next = new Set(expandedIds.value)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    expandedIds.value = next
  }

  /** 判断某版本内容是否处于展开状态 */
  const isExpanded = (id: number): boolean => expandedIds.value.has(id)

  /** 判断内容长度是否需要折叠 */
  const needCollapse = (content: string): boolean => content.length > PREVIEW_MAX_CHARS

  /** 获取内容预览（超长截断并补省略号） */
  const getPreview = (content: string): string => {
    if (content.length <= PREVIEW_MAX_CHARS) return content
    return content.slice(0, PREVIEW_MAX_CHARS) + '...'
  }

  /** 打开注册新版本对话框，可预填 key */
  const openRegisterDialog = (presetKey?: string): void => {
    registerForm.prompt_key = presetKey ?? selectedKey.value ?? ''
    registerForm.content = ''
    registerForm.description = ''
    registerDialogVisible.value = true
  }

  /** 提交注册新版本 */
  const submitRegister = async (): Promise<void> => {
    if (!registerFormRef.value) return
    try {
      await registerFormRef.value.validate()
    } catch {
      // 校验未通过，el-form 会展示字段级错误提示
      return
    }
    actionLoading.value = true
    try {
      const payload: PromptTemplateCreate = {
        prompt_key: registerForm.prompt_key,
        content: registerForm.content,
        description: registerForm.description || undefined,
      }
      await promptTemplateApi.registerVersion(payload)
      ElMessage.success('新版本注册成功')
      registerDialogVisible.value = false
      // 注册后选中新版本所属 key，便于立即查看
      selectedKey.value = registerForm.prompt_key
      await loadAll()
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '注册新版本失败'
      ElMessage.error(msg)
    } finally {
      actionLoading.value = false
    }
  }

  /** 设为默认版本（二次确认） */
  const setDefault = (row: PromptTemplate): void => {
    ElMessageBox.confirm(
      `确定将「${row.prompt_key}」的版本 v${row.prompt_version} 设为默认吗？此操作会取消其他版本的默认标记。`,
      '确认设为默认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
      .then(async () => {
        actionLoading.value = true
        try {
          await promptTemplateApi.setDefault(row.prompt_key, row.prompt_version)
          ElMessage.success('已设为默认版本')
          await loadAll()
        } catch (error: unknown) {
          const msg = error instanceof Error ? error.message : '设为默认失败'
          ElMessage.error(msg)
        } finally {
          actionLoading.value = false
        }
      })
      .catch(() => {
        /* 用户取消，无需处理 */
      })
  }

  /** 回滚到指定版本（二次确认） */
  const rollback = (row: PromptTemplate): void => {
    ElMessageBox.confirm(
      `确定回滚「${row.prompt_key}」到版本 v${row.prompt_version} 吗？该版本将设为默认并启用，高于该版本的将被禁用。`,
      '确认回滚',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
      .then(async () => {
        actionLoading.value = true
        try {
          await promptTemplateApi.rollback(row.prompt_key, row.prompt_version)
          ElMessage.success('回滚成功')
          await loadAll()
        } catch (error: unknown) {
          const msg = error instanceof Error ? error.message : '回滚失败'
          ElMessage.error(msg)
        } finally {
          actionLoading.value = false
        }
      })
      .catch(() => {
        /* 用户取消，无需处理 */
      })
  }

  /** ISO 时间字符串格式化为 YYYY-MM-DD HH:mm */
  const formatTime = (iso: string): string => {
    if (!iso) return '-'
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return iso
    const pad = (n: number): string => String(n).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  /** 截断 SHA256 哈希用于展示（保留首尾各 8 位） */
  const shortHash = (hash: string): string => {
    if (!hash || hash.length <= 16) return hash
    return `${hash.slice(0, 8)}...${hash.slice(-8)}`
  }

  /** 判断当前 key 内是否存在与指定版本哈希相同的其他版本 */
  const hasSameHashElsewhere = (row: PromptTemplate): boolean => {
    if (!currentRegistry.value) return false
    return currentRegistry.value.versions.some(
      (v) => v.id !== row.id && v.prompt_hash === row.prompt_hash
    )
  }

  onMounted(() => {
    loadAll()
  })

  return {
    loading,
    actionLoading,
    registries,
    filteredRegistries,
    filterText,
    selectedKey,
    currentRegistry,
    currentVersions,
    expandedIds,
    registerDialogVisible,
    registerFormRef,
    registerForm,
    registerRules,
    selectKey,
    toggleExpand,
    isExpanded,
    needCollapse,
    getPreview,
    openRegisterDialog,
    submitRegister,
    setDefault,
    rollback,
    formatTime,
    shortHash,
    hasSameHashElsewhere,
  }
}
