import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

const { mockPush, mockRoute, mockHasPermission, mockFlowSortReset, mockElMessage } = vi.hoisted(
  () => ({
    mockPush: vi.fn(),
    mockRoute: { path: '/home/project' },
    mockHasPermission: vi.fn(),
    mockFlowSortReset: vi.fn(),
    mockElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  })
)

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => mockRoute,
}))
vi.mock('element-plus', () => ({ ElMessage: mockElMessage }))
vi.mock('@/store/flowSort', () => ({
  useFlowSortStore: () => ({ reset: mockFlowSortReset }),
}))
vi.mock('@/directives/permission', () => ({ hasPermission: mockHasPermission }))
vi.mock('@element-plus/icons-vue', () => ({
  HomeFilled: {},
  DataAnalysis: {},
  Setting: {},
  Message: {},
  Check: {},
  Timer: {},
  DataLine: {},
  Lightning: {},
}))

import { useMainLayout } from '../useMainLayout'

function withSetup(path = '/home/project') {
  mockRoute.path = path
  let api!: ReturnType<typeof useMainLayout>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useMainLayout()
        return () => null
      },
    })
  )
  return { api, wrapper }
}

describe('useMainLayout — 菜单权限过滤', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHasPermission.mockReturnValue(true)
  })

  it('全部有权限时菜单结构完整（含 3 个分组）', () => {
    const { api, wrapper } = withSetup()

    const groups = api.menuItems.value.filter((item) => item.children)
    expect(groups.map((g) => g.index)).toEqual(['case', 'iteration', 'system'])
    expect(api.menuItems.value.map((i) => i.index)).toContain('/home/quick-test')

    wrapper.unmount()
  })

  it('无权限的子项被过滤，分组保留其余子项', () => {
    mockHasPermission.mockImplementation((perm?: string) => perm !== 'system:manage')
    const { api, wrapper } = withSetup()

    const system = api.menuItems.value.find((item) => item.index === 'system')
    expect(system?.children?.map((c) => c.index)).toEqual([
      '/home/system/user',
      '/home/system/role',
    ])

    wrapper.unmount()
  })

  it('子项全部无权限时整个分组移除', () => {
    mockHasPermission.mockImplementation((perm?: string) => perm === undefined || perm === null)
    const { api, wrapper } = withSetup()

    expect(api.menuItems.value.some((item) => item.index === 'system')).toBe(false)

    wrapper.unmount()
  })
})

describe('useMainLayout — activeMenu 映射', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHasPermission.mockReturnValue(true)
  })

  it.each([
    ['/home/project/detail/12', '/home/project'],
    ['/home/case/detail/3', '/home/case'],
    ['/home/case/quality/3', '/home/case'],
    ['/home/case/test-point-extract', '/home/case/test-point-management'],
    ['/home/case/pipeline/run-1', '/home/pipeline-dashboard'],
    ['/home/requirement/ui-prototype/8', '/home/requirement'],
    ['/home/analysis', '/home/requirement'],
    ['/home/task/detail/5', '/home/task'],
    ['/home/report/detail/2', '/home/report'],
  ])('子路径 %s 高亮 %s', (path, expected) => {
    const { api, wrapper } = withSetup(path)

    expect(api.activeMenu.value).toBe(expected)

    wrapper.unmount()
  })

  it('未命中映射时回退为当前路径', () => {
    const { api, wrapper } = withSetup('/home/system/user')

    expect(api.activeMenu.value).toBe('/home/system/user')

    wrapper.unmount()
  })
})

describe('useMainLayout — 面包屑', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHasPermission.mockReturnValue(true)
  })

  it('/home/case 末尾追加「用例列表」', () => {
    const { api, wrapper } = withSetup('/home/case')

    // 既有行为：/home 无映射项，因此「测试资产」与追加的「用例列表」共用 /home/case
    expect(api.breadcrumbList.value).toEqual([
      { path: '/home/case', name: '测试资产' },
      { path: '/home/case', name: '用例列表' },
    ])

    wrapper.unmount()
  })

  it('/home/pipeline-dashboard 前插入「迭代中心」', () => {
    const { api, wrapper } = withSetup('/home/pipeline-dashboard')

    expect(api.breadcrumbList.value.map((i) => i.name)).toEqual(['迭代中心', 'Pipeline仪表盘'])

    wrapper.unmount()
  })

  it('未知片段被忽略，仅保留可映射层级', () => {
    const { api, wrapper } = withSetup('/home/task/unknown-segment')

    expect(api.breadcrumbList.value).toEqual([{ path: '/home/task', name: '执行中心' }])

    wrapper.unmount()
  })
})

describe('useMainLayout — 侧边栏与用户操作', () => {
  const originalWidth = window.innerWidth

  beforeEach(() => {
    vi.clearAllMocks()
    mockHasPermission.mockReturnValue(true)
    localStorage.clear()
    Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true, writable: true })
  })

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      value: originalWidth,
      configurable: true,
      writable: true,
    })
  })

  it('桌面端 toggleSidebar 切换 collapsed', () => {
    const { api, wrapper } = withSetup()

    expect(api.isMobile.value).toBe(false)
    api.toggleSidebar()
    expect(api.sidebarCollapsed.value).toBe(true)
    api.toggleSidebar()
    expect(api.sidebarCollapsed.value).toBe(false)

    wrapper.unmount()
  })

  it('移动端 toggleSidebar 切换 expanded，选中菜单后自动收起', () => {
    const { api, wrapper } = withSetup()

    window.innerWidth = 500
    window.dispatchEvent(new Event('resize'))
    expect(api.isMobile.value).toBe(true)

    api.toggleSidebar()
    expect(api.sidebarExpanded.value).toBe(true)

    api.handleMenuSelect()
    expect(api.sidebarExpanded.value).toBe(false)

    wrapper.unmount()
  })

  it('handleProfile 跳转个人中心', () => {
    const { api, wrapper } = withSetup()

    api.handleProfile()

    expect(mockPush).toHaveBeenCalledWith('/home/system/profile')

    wrapper.unmount()
  })

  it('handleLogout 清理 token、重置 flowSort、提示并跳转登录页', () => {
    localStorage.setItem('token', 'abc')
    const { api, wrapper } = withSetup()

    api.handleLogout()

    expect(localStorage.getItem('token')).toBeNull()
    expect(mockFlowSortReset).toHaveBeenCalledTimes(1)
    expect(mockElMessage.success).toHaveBeenCalledWith('退出登录成功')
    expect(mockPush).toHaveBeenCalledWith('/login')

    wrapper.unmount()
  })

  it('卸载后移除 resize 监听，避免内存泄漏', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { wrapper } = withSetup()

    wrapper.unmount()
    await nextTick()

    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    removeSpy.mockRestore()
  })
})
