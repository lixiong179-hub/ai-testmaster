import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useFlowSortStore } from '@/store/flowSort'

export function useMainLayout() {
  const router = useRouter()
  const route = useRoute()

  const isMobile = ref(false)
  const sidebarExpanded = ref(false)
  const username = ref('测试管理员')
  const userAvatar = ref('')

  const activeMenu = computed(() => route.path)

  const breadcrumbList = ref<{ path: string; name: string }[]>([])

  const breadcrumbMap: Record<string, string> = {
    '/home/dashboard': '仪表盘',
    '/home/project': '项目列表',
    '/home/project/detail': '项目详情',
    '/home/requirement': '资源管理',
    '/home/requirement/upload': '上传需求',
    '/home/requirement/ui-prototype': 'UI原型图',
    '/home/case': '测试用例管理',
    '/home/case/test-point-management': '测试点管理',
    '/home/case/ai-generate': 'AI生成用例',
    '/home/task': '测试任务管理',
    '/home/report': '测试报告',
    '/home/system': '系统管理',
    '/home/system/user': '用户管理',
    '/home/system/role': '角色管理',
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
    breadcrumbList.value = result
  }

  watch(() => route.path, (newPath) => { updateBreadcrumb(newPath) }, { immediate: true })

  const checkMobile = () => { isMobile.value = window.innerWidth <= 768 }

  const toggleSidebar = () => { if (isMobile.value) sidebarExpanded.value = !sidebarExpanded.value }

  const handleMenuSelect = () => { if (isMobile.value) sidebarExpanded.value = false }

  const handleProfile = () => { router.push('/home/system/profile') }

  const handleLogout = () => {
    localStorage.removeItem('token')
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
    ElMessage.success('退出登录成功')
    router.push('/login')
  }

  onMounted(() => { checkMobile(); window.addEventListener('resize', checkMobile) })
  onUnmounted(() => { window.removeEventListener('resize', checkMobile) })

  return {
    isMobile, sidebarExpanded, username, userAvatar, activeMenu, breadcrumbList,
    toggleSidebar, handleMenuSelect, handleProfile, handleLogout,
  }
}
