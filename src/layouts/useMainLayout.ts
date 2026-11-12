import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useFlowSortStore } from '@/store/flowSort'
import { MENU_CONFIG, filterMenuByPermission, breadcrumbMap, type MenuItem } from './menuConfig'

export type { MenuItem }

// 收集所有叶子菜单的 index，用于侧边栏高亮匹配
const collectLeafIndices = (items: MenuItem[]): string[] =>
  items.flatMap((item) =>
    item.children && item.children.length > 0 ? collectLeafIndices(item.children) : [item.index]
  )

const LEAF_INDICES = collectLeafIndices(MENU_CONFIG)

// 详情页/隐藏子路由 → 所属菜单项 index，保证侧边栏高亮不丢失
const ACTIVE_MENU_ALIASES: Record<string, string> = {
  '/home/case/test-point-extract': '/home/case/test-point-management',
  '/home/case/pipeline': '/home/pipeline-dashboard',
  '/home/case/iteration/regression-generate': '/home/iteration/list',
  '/home/iteration/pipeline': '/home/pipeline-dashboard',
  '/home/iteration/review': '/home/iteration/review/0',
  '/home/iteration/regression-generate': '/home/iteration/list',
  '/home/requirement/upload': '/home/requirement',
  '/home/analysis': '/home/requirement/analysis',
  // 旧路径兼容（/home/report、/home/bug 已重定向至执行中心）
  '/home/report': '/home/execution/report',
  '/home/bug': '/home/execution/bug',
}

const resolveActiveMenu = (path: string): string => {
  // 1. 精确命中菜单项
  const exact = LEAF_INDICES.find((index) => index === path)
  if (exact) return exact

  // 2. 显式别名（隐藏子路由）
  const aliasKey = Object.keys(ACTIVE_MENU_ALIASES)
    .filter((prefix) => path === prefix || path.startsWith(prefix + '/'))
    .sort((a, b) => b.length - a.length)[0]
  if (aliasKey) return ACTIVE_MENU_ALIASES[aliasKey]

  // 3. 最长前缀匹配（如 /home/task/detail/1 → /home/task）
  const prefixed = LEAF_INDICES.filter((index) => path.startsWith(index + '/')).sort(
    (a, b) => b.length - a.length
  )[0]
  if (prefixed) return prefixed

  return path
}

export function useMainLayout() {
  const router = useRouter()
  const route = useRoute()

  const isMobile = ref(false)
  const sidebarExpanded = ref(false)
  const sidebarCollapsed = ref(false)
  const username = ref('测试管理员')
  const userAvatar = ref('')

  const menuItems = computed(() => filterMenuByPermission(MENU_CONFIG))

  const activeMenu = computed(() => resolveActiveMenu(route.path))

  const breadcrumbList = ref<{ path: string; name: string }[]>([])

  const updateBreadcrumb = (path: string) => {
    const pathParts = path.split('/').filter(Boolean)
    const result: { path: string; name: string }[] = []
    let currentPath = ''
    for (let i = 0; i < pathParts.length; i++) {
      currentPath += '/' + pathParts[i]
      const name = breadcrumbMap[currentPath]
      if (name) result.push({ path: currentPath, name })
    }
    if (
      path === '/home/case' &&
      result.length > 0 &&
      result[result.length - 1].name === '测试资产'
    ) {
      result.push({ path: '/home/case', name: '用例列表' })
    }
    if (path === '/home/pipeline-dashboard' && result.length > 0) {
      const idx = result.findIndex((r) => r.name === 'Pipeline仪表盘')
      if (idx >= 0) {
        result.splice(idx, 0, { path: '/home/ops', name: '运营看板' })
      }
    }
    breadcrumbList.value = result
  }

  watch(
    () => route.path,
    (newPath) => {
      updateBreadcrumb(newPath)
    },
    { immediate: true }
  )

  const checkMobile = () => {
    isMobile.value = window.innerWidth <= 768
    if (isMobile.value) sidebarCollapsed.value = false
  }

  const toggleSidebar = () => {
    if (isMobile.value) {
      sidebarExpanded.value = !sidebarExpanded.value
      return
    }
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const handleMenuSelect = () => {
    if (isMobile.value) sidebarExpanded.value = false
  }

  const handleProfile = () => {
    router.push('/home/system/profile')
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
    ElMessage.success('退出登录成功')
    router.push('/login')
  }

  onMounted(() => {
    checkMobile()
    window.addEventListener('resize', checkMobile)
  })
  onUnmounted(() => {
    window.removeEventListener('resize', checkMobile)
  })

  return {
    isMobile,
    sidebarExpanded,
    sidebarCollapsed,
    username,
    userAvatar,
    activeMenu,
    breadcrumbList,
    menuItems,
    toggleSidebar,
    handleMenuSelect,
    handleProfile,
    handleLogout,
  }
}
