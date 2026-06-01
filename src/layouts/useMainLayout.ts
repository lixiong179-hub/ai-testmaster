import { ref, computed, watch, onMounted, onUnmounted, type Component } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  HomeFilled,
  DataAnalysis,
  Setting,
  Message,
  Check,
  Timer,
  DataLine,
} from '@element-plus/icons-vue'
import { useFlowSortStore } from '@/store/flowSort'
import { hasPermission } from '@/directives/permission'

export interface MenuItem {
  index: string
  label: string
  icon?: Component
  permission?: string
  children?: MenuItem[]
}

const MENU_CONFIG: MenuItem[] = [
  { index: '/home/project', label: '项目中心', icon: HomeFilled },
  { index: '/home/requirement', label: '资源中心', icon: Message },
  {
    index: 'case',
    label: '测试资产',
    icon: Check,
    children: [
      { index: '/home/case/smart-generate', label: '智能生成用例' },
      { index: '/home/case/test-point-management', label: '测试点管理' },
      { index: '/home/case', label: '用例列表' },
      { index: '/home/case/ai-generate', label: 'AI生成用例' },
      { index: '/home/case/migration', label: '用例迁移' },
      { index: '/home/case/case-refresh', label: '保鲜建议' },
    ],
  },
  { index: '/home/task', label: '执行中心', icon: Timer },
  { index: '/home/report', label: '报告中心', icon: DataAnalysis },
  {
    index: 'iteration',
    label: '迭代中心',
    icon: DataLine,
    children: [
      { index: '/home/pipeline-dashboard', label: 'Pipeline仪表盘' },
      { index: '/home/iteration/regression-generate', label: '回归变更分析' },
    ],
  },
  {
    index: 'system',
    label: '系统管理',
    icon: Setting,
    children: [
      { index: '/home/system/user', label: '用户管理', permission: 'user:list' },
      { index: '/home/system/role', label: '角色管理', permission: 'role:list' },
      { index: '/home/system/audit-log', label: '审计日志', permission: 'system:manage' },
      { index: '/home/system/test-capability', label: '测试能力', permission: 'system:manage' },
    ],
  },
]

function filterMenuByPermission(items: MenuItem[]): MenuItem[] {
  return items
    .map((item) => {
      if (!hasPermission(item.permission)) return null
      if (item.children) {
        const filteredChildren = filterMenuByPermission(item.children)
        if (filteredChildren.length === 0) return null
        return { ...item, children: filteredChildren }
      }
      return item
    })
    .filter((item): item is MenuItem => item !== null)
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

  const activeMenu = computed(() => {
    if (route.path.startsWith('/home/project/detail')) return '/home/project'
    if (route.path.startsWith('/home/case/detail/')) return '/home/case'
    if (route.path.startsWith('/home/case/quality/')) return '/home/case'
    if (route.path.startsWith('/home/case/test-point-extract'))
      return '/home/case/test-point-management'
    if (route.path.startsWith('/home/case/smart-generate')) return '/home/case/smart-generate'
    if (route.path.startsWith('/home/case/ai-generate')) return '/home/case/ai-generate'
    if (route.path.startsWith('/home/case/migration')) return '/home/case/migration'
    if (route.path.startsWith('/home/case/case-refresh')) return '/home/case/case-refresh'
    if (route.path.startsWith('/home/case/iteration/regression-generate'))
      return '/home/iteration/regression-generate'
    if (route.path.startsWith('/home/case/pipeline/')) return '/home/pipeline-dashboard'
    if (route.path.startsWith('/home/iteration/pipeline/')) return '/home/pipeline-dashboard'
    if (route.path.startsWith('/home/iteration/regression-generate'))
      return '/home/iteration/regression-generate'
    if (route.path.startsWith('/home/requirement/ui-prototype')) return '/home/requirement'
    if (route.path.startsWith('/home/requirement/upload')) return '/home/requirement'
    if (route.path.startsWith('/home/analysis')) return '/home/requirement'
    if (route.path.startsWith('/home/task/')) return '/home/task'
    if (route.path.startsWith('/home/report/')) return '/home/report'
    return route.path
  })

  const breadcrumbList = ref<{ path: string; name: string }[]>([])

  const breadcrumbMap: Record<string, string> = {
    '/home/dashboard': '仪表盘',
    '/home/project': '项目中心',
    '/home/project/detail': '项目详情',
    '/home/requirement': '资源中心',
    '/home/requirement/upload': '上传资源',
    '/home/requirement/ui-prototype': 'UI原型详情',
    '/home/case': '测试资产',
    '/home/case/detail': '用例详情',
    '/home/case/test-point-management': '测试点管理',
    '/home/case/test-point-extract': '测试点提取',
    '/home/case/ai-generate': 'AI生成用例',
    '/home/case/smart-generate': '智能生成用例',
    '/home/case/migration': '用例迁移',
    '/home/case/case-refresh': '保鲜建议',
    '/home/case/quality': '用例质量分析',
    '/home/case/iteration/regression-generate': '回归变更分析',
    '/home/task': '执行中心',
    '/home/task/list': '任务列表',
    '/home/task/create': '创建任务',
    '/home/task/detail': '任务详情',
    '/home/task/execution': '测试执行',
    '/home/report': '报告中心',
    '/home/report/detail': '报告详情',
    '/home/pipeline-dashboard': 'Pipeline仪表盘',
    '/home/iteration': '迭代中心',
    '/home/iteration/pipeline': 'Pipeline进度',
    '/home/iteration/regression-generate': '回归变更分析',
    '/home/system': '系统管理',
    '/home/system/user': '用户管理',
    '/home/system/role': '角色管理',
    '/home/system/audit-log': '审计日志',
    '/home/system/test-capability': '测试能力',
    '/home/system/profile': '个人中心',
    '/home/analysis': '需求分析',
  }

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
        result.splice(idx, 0, { path: '/home/iteration', name: '迭代中心' })
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
