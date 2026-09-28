import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// ==================== Mock 准备（hoisted 保证 vi.mock 工厂可用） ====================
const { mockRouter, mockAuthApi } = vi.hoisted(() => ({
    mockRouter: {
        push: vi.fn(),
        currentRoute: { value: { query: {} } },
    },
    mockAuthApi: {
        generateCaptcha: vi.fn(),
        login: vi.fn(),
        register: vi.fn(),
        getCurrentUser: vi.fn(),
    },
}))

vi.mock('vue-router', () => ({
    useRouter: () => mockRouter,
}))

vi.mock('element-plus', () => ({
    ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

// Mock @/api/auth：避免加载 request.ts（其内部 import @/router 产生副作用）
vi.mock('@/api/auth', () => ({
    authApi: mockAuthApi,
    default: mockAuthApi,
}))

import Login from '../index.vue'

function mountLogin() {
    return mount(Login)
}

describe('Login 登录页', () => {
    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        // 使用假定时器，避免 onMounted 中 setTimeout(refreshCaptcha, 100) 在用例间泄漏
        vi.useFakeTimers()
        setActivePinia(createPinia())
        // 验证码接口默认返回图片，避免触发 canvas 兜底分支
        mockAuthApi.generateCaptcha.mockResolvedValue({
            code: 200,
            data: { captcha_id: 'cap-1', image: 'base64img' },
        })
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    describe('Task A-01: 手机登录 Tab 禁用', () => {
        it('渲染账号登录与手机登录两个 Tab', async () => {
            const wrapper = mountLogin()
            await flushPromises()

            const tabItems = wrapper.findAll('.el-tabs__item')
            expect(tabItems).toHaveLength(2)
            expect(tabItems[0].text()).toContain('账号登录')
            expect(tabItems[1].text()).toContain('手机登录')
        })

        it('手机登录 Tab 的 el-tab-pane 携带 disabled 属性', async () => {
            const wrapper = mountLogin()
            await flushPromises()

            const panes = wrapper.findAllComponents({ name: 'ElTabPane' })
            const phonePane = panes.find((p) => p.props('name') === 'phone')
            expect(phonePane).toBeTruthy()
            expect(phonePane!.props('disabled')).toBe(true)
        })

        it('手机登录 Tab 导航项带 is-disabled 禁用样式类', async () => {
            const wrapper = mountLogin()
            await flushPromises()

            const phoneTabItem = wrapper
                .findAll('.el-tabs__item')
                .find((el) => el.text().includes('手机登录'))
            expect(phoneTabItem).toBeTruthy()
            expect(phoneTabItem!.classes()).toContain('is-disabled')
        })

        it('鼠标悬停 tooltip 内容包含"即将上线"', async () => {
            const wrapper = mountLogin()
            await flushPromises()

            const tooltip = wrapper.findComponent({ name: 'ElTooltip' })
            expect(tooltip.exists()).toBe(true)
            expect(tooltip.props('content')).toContain('即将上线')
        })

        it('点击手机登录 Tab 不会切换，activeTab 始终为 account', async () => {
            const wrapper = mountLogin()
            await flushPromises()

            const tabItems = wrapper.findAll('.el-tabs__item')
            const accountTabItem = tabItems.find((el) => el.text().includes('账号登录'))
            const phoneTabItem = tabItems.find((el) => el.text().includes('手机登录'))
            expect(accountTabItem).toBeTruthy()
            expect(phoneTabItem).toBeTruthy()

            await phoneTabItem!.trigger('click')
            await flushPromises()

            // 账号登录仍为激活态，手机登录未激活
            expect(accountTabItem!.classes()).toContain('is-active')
            expect(phoneTabItem!.classes()).not.toContain('is-active')
        })
    })
})
