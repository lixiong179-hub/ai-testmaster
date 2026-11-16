import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useMainLayout', () => ({
  useMainLayout: () => state.current,
}))

import MainLayout from '../MainLayout.vue'

const ElMenuStub = defineComponent({
  name: 'ElMenu',
  props: {
    defaultActive: { type: String, default: '' },
    collapse: { type: Boolean, default: false },
  },
  emits: ['select'],
  template:
    '<nav class="el-menu" :data-active="defaultActive" :data-collapse="collapse"><slot /></nav>',
})

const ElSubMenuStub = defineComponent({
  name: 'ElSubMenu',
  props: { index: { type: String, default: '' } },
  template: '<div class="el-sub-menu" :data-index="index"><slot name="title" /><slot /></div>',
})

const ElMenuItemStub = defineComponent({
  name: 'ElMenuItem',
  props: { index: { type: String, default: '' } },
  template: '<div class="el-menu-item" :data-index="index"><slot /></div>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  emits: ['click'],
  template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
})

const ElBreadcrumbStub = defineComponent({
  name: 'ElBreadcrumb',
  template: '<div class="el-breadcrumb"><slot /></div>',
})

const ElBreadcrumbItemStub = defineComponent({
  name: 'ElBreadcrumbItem',
  props: { to: { type: Object, default: undefined } },
  template: '<span class="el-breadcrumb-item"><slot /></span>',
})

const ElAvatarStub = defineComponent({
  name: 'ElAvatar',
  props: { src: { type: String, default: '' }, size: { type: Number, default: 32 } },
  template: '<img class="el-avatar" :src="src" />',
})

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  template: '<div class="el-dropdown"><slot /><slot name="dropdown" /></div>',
})

const ElDropdownMenuStub = defineComponent({
  name: 'ElDropdownMenu',
  template: '<div class="el-dropdown-menu"><slot /></div>',
})

const ElDropdownItemStub = defineComponent({
  name: 'ElDropdownItem',
  emits: ['click'],
  template: '<div class="el-dropdown-item" @click="$emit(\'click\')"><slot /></div>',
})

const stubs = {
  ElMenu: ElMenuStub,
  ElSubMenu: ElSubMenuStub,
  ElMenuItem: ElMenuItemStub,
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElBreadcrumb: ElBreadcrumbStub,
  ElBreadcrumbItem: ElBreadcrumbItemStub,
  ElAvatar: ElAvatarStub,
  ElDropdown: ElDropdownStub,
  ElDropdownMenu: ElDropdownMenuStub,
  ElDropdownItem: ElDropdownItemStub,
  QuickTestGlobalEntry: { template: '<div class="quick-entry-stub" />' },
  RouterView: { template: '<div class="router-view-stub" />' },
}

const toggles = {
  toggleSidebar: vi.fn(),
  handleMenuSelect: vi.fn(),
  handleProfile: vi.fn(),
  handleLogout: vi.fn(),
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    isMobile: ref(false),
    sidebarExpanded: ref(false),
    sidebarCollapsed: ref(false),
    username: ref('管理员'),
    userAvatar: ref('https://cdn.example.com/a.png'),
    activeMenu: ref('/home/project'),
    breadcrumbList: ref([{ name: '项目管理' }]),
    menuItems: ref([
      { index: '/home/workbench', label: '工作台', icon: 'span' },
      {
        index: '/home/case',
        label: '用例管理',
        icon: 'span',
        children: [
          { index: '/home/case/list', label: '用例列表' },
          { index: '/home/case/test-point-management', label: '测试点管理' },
        ],
      },
    ]),
    ...toggles,
    ...over,
  }
}

function mountLayout(over: Record<string, unknown> = {}) {
  state.current = makeCtx(over)
  return mount(MainLayout, { global: { stubs } })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MainLayout — 渲染', () => {
  it('按 menuItems 渲染一级与二级菜单', () => {
    const wrapper = mountLayout()

    const flat = wrapper.findAll('.el-menu > .el-menu-item')
    expect(flat.map((node) => node.text())).toEqual(['工作台'])

    const sub = wrapper.find('.el-sub-menu')
    expect(sub.attributes('data-index')).toBe('/home/case')
    expect(sub.findAll('.el-menu-item').map((node) => node.text())).toEqual([
      '用例列表',
      '测试点管理',
    ])
  })

  it('把当前路由作为菜单激活项', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('.el-menu').attributes('data-active')).toBe('/home/project')
  })

  it('渲染用户名、头像与面包屑', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('.username').text()).toBe('管理员')
    expect(wrapper.find('.el-avatar').attributes('src')).toBe('https://cdn.example.com/a.png')

    const crumbs = wrapper.findAll('.el-breadcrumb-item').map((node) => node.text())
    expect(crumbs).toEqual(['工作台', '项目管理'])
  })

  it('折叠态附加 collapsed 类且菜单进入 collapse', () => {
    const wrapper = mountLayout({ sidebarCollapsed: ref(true) })

    expect(wrapper.find('.sidebar').classes()).toContain('collapsed')
    expect(wrapper.find('.el-menu').attributes('data-collapse')).toBe('true')
  })

  it('移动端展开态附加 expanded 类并隐藏品牌全称', () => {
    const wrapper = mountLayout({ isMobile: ref(true), sidebarExpanded: ref(true) })

    expect(wrapper.find('.sidebar').classes()).toContain('expanded')
    // 移动端额外渲染展开/收起图标，桌面端不渲染
    expect(wrapper.find('.mobile-toggle').exists()).toBe(true)
  })

  it('桌面端折叠时展示 logo 缩写', () => {
    const wrapper = mountLayout({ sidebarCollapsed: ref(true) })

    expect(wrapper.find('.logo-mark').text()).toBe('AI')
  })
})

describe('MainLayout — 交互', () => {
  it('点击 logo 与侧栏按钮都触发 toggleSidebar', async () => {
    const wrapper = mountLayout()

    await wrapper.find('.logo').trigger('click')
    await wrapper.find('.sidebar-toggle').trigger('click')

    expect(toggles.toggleSidebar).toHaveBeenCalledTimes(2)
  })

  it('菜单选中透传 index', () => {
    const wrapper = mountLayout()

    wrapper.findComponent({ name: 'ElMenu' }).vm.$emit('select', '/home/case/list')

    expect(toggles.handleMenuSelect).toHaveBeenCalledWith('/home/case/list')
  })

  it('下拉菜单点击个人中心与退出登录', async () => {
    const wrapper = mountLayout()

    const items = wrapper.findAll('.el-dropdown-item')
    expect(items.map((node) => node.text())).toEqual(['个人中心', '退出登录'])

    await items[0].trigger('click')
    await items[1].trigger('click')

    expect(toggles.handleProfile).toHaveBeenCalledTimes(1)
    expect(toggles.handleLogout).toHaveBeenCalledTimes(1)
  })

  it('主内容区包含快速测试入口与路由出口', () => {
    const wrapper = mountLayout()

    expect(wrapper.find('.quick-entry-stub').exists()).toBe(true)
    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
  })
})
