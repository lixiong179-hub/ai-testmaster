import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h, type Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import ProjectDetail from '../detail.vue'
import QualityRuleTab from '../components/QualityRuleTab.vue'
import TestCapabilityTab from '../components/TestCapabilityTab.vue'
import { routes } from '@/router/routes'
import type { Project, ProjectDetailResponse } from '@/api/project'

// ==================== Mock 准备（hoisted 保证 vi.mock 工厂可用） ====================

const {
    mockRoute,
    mockPush,
    getProjectDetailMock,
    getQualityRulesMock,
    updateQualityRuleMock,
    getTestCapabilitiesMock,
} = vi.hoisted(() => ({
    // 路由 query 可变，用例动态设置 project_id / tab
    mockRoute: {
        query: {} as Record<string, string>,
        params: {} as Record<string, string>,
    },
    mockPush: vi.fn().mockResolvedValue(undefined),
    getProjectDetailMock: vi.fn(),
    getQualityRulesMock: vi.fn(),
    updateQualityRuleMock: vi.fn(),
    getTestCapabilitiesMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
    useRoute: () => mockRoute,
    useRouter: () => ({ push: mockPush }),
    createRouter: vi.fn(() => ({ push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn() })),
    createWebHistory: vi.fn(),
}))

vi.mock('@/router', () => ({
    default: { push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn(), onError: vi.fn() },
}))

vi.mock('@/api/project', () => ({
    ProjectAPI: {
        getProjectDetail: getProjectDetailMock,
        getProjects: vi.fn().mockResolvedValue({ data: { items: [] } }),
        getProjectList: vi.fn().mockResolvedValue({ data: { items: [] } }),
        updateProjectConfig: vi.fn(),
    },
}))

// 屏蔽 file API 链，避免加载真实 request.ts → @/router 副作用
vi.mock('@/api/file', () => ({
    FileAPI: { uploadFile: vi.fn(), submitUrl: vi.fn(), deleteFile: vi.fn() },
}))

vi.mock('@/api/qualityRule', () => ({
    qualityRuleApi: {
        getQualityRules: getQualityRulesMock,
        updateQualityRule: updateQualityRuleMock,
    },
}))

vi.mock('@/api/testCapability', () => ({
    testCapabilityApi: {
        getList: getTestCapabilitiesMock,
        create: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
    },
}))

// ==================== 子组件桩（避免渲染兄弟 Tab 的依赖） ====================

const RequirementUploaderStub = defineComponent({
    name: 'RequirementUploader',
    setup() {
        return () => h('div', { class: 'stub-uploader' })
    },
})
const SelfHealingConfigTabStub = defineComponent({
    name: 'SelfHealingConfigTab',
    setup() {
        return () => h('div', { class: 'stub-self-healing' })
    },
})

/** 质量规则 Tab 桩：捕获 projectId 供断言 */
function makeQualityRuleTabStub() {
    return defineComponent({
        name: 'QualityRuleTab',
        props: { projectId: { type: Number, required: true } },
        setup(props) {
            return () =>
                h('div', {
                    class: 'stub-quality-rule',
                    'data-project-id': String(props.projectId),
                })
        },
    })
}

/** 测试能力 Tab 桩：捕获 projectId 供断言 */
function makeTestCapabilityTabStub() {
    return defineComponent({
        name: 'TestCapabilityTab',
        props: { projectId: { type: Number, required: true } },
        setup(props) {
            return () =>
                h('div', {
                    class: 'stub-test-capability',
                    'data-project-id': String(props.projectId),
                })
        },
    })
}

// ==================== 测试数据工厂 ====================

function makeProject(overrides: Partial<Project> = {}): Project {
    return {
        id: 1,
        name: '测试项目',
        description: '描述',
        project_type: 'web',
        status: 1,
        create_time: '2026-07-30 10:00:00',
        update_time: '2026-07-30 10:00:00',
        source: 'manual',
        ...overrides,
    }
}

function makeDetailResponse(project: Project): ProjectDetailResponse {
    return { code: 200, message: 'ok', data: { ...project, files: [] } }
}

/** 挂载 ProjectDetail，默认桩掉 QualityRuleTab/TestCapabilityTab 以聚焦 Tab 结构与 prop 传递 */
function mountDetail(opts: {
    projectId?: number
    tab?: string
    realQualityRule?: boolean
    realTestCapability?: boolean
} = {}) {
    const { projectId = 1, tab, realQualityRule = false, realTestCapability = false } = opts
    mockRoute.query = tab
        ? { project_id: String(projectId), tab }
        : { project_id: String(projectId) }
    getProjectDetailMock.mockResolvedValue(makeDetailResponse(makeProject({ id: projectId })))
    const stubs: Record<string, Component> = {
        RequirementUploader: RequirementUploaderStub,
        SelfHealingConfigTab: SelfHealingConfigTabStub,
    }
    if (!realQualityRule) stubs.QualityRuleTab = makeQualityRuleTabStub()
    if (!realTestCapability) stubs.TestCapabilityTab = makeTestCapabilityTabStub()
    return mount(ProjectDetail, { global: { stubs } })
}

/** 在路由树中按 path 查找路由记录 */
function findRouteByPath(
    list: RouteRecordRaw[],
    path: string
): RouteRecordRaw | undefined {
    for (const r of list) {
        if (r.path === path) return r
        if (r.children) {
            const found = findRouteByPath(r.children as RouteRecordRaw[], path)
            if (found) return found
        }
    }
    return undefined
}

describe('ProjectDetail 质量规则 Tab 迁移（Task 8）', () => {
    let wrapper: VueWrapper | null

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        // 每个用例独立 pinia，useProjectDetail 内部 useProjectStore() 取到隔离实例
        setActivePinia(createPinia())
        getQualityRulesMock.mockResolvedValue({ data: [] })
        getTestCapabilitiesMock.mockResolvedValue({ data: [] })
        wrapper = null
    })

    afterEach(() => {
        // unmount 触发 onUnmounted -> resetState，避免状态残留
        wrapper?.unmount()
        wrapper = null
        vi.restoreAllMocks()
    })

    describe('SubTask 8.1 - Tab 存在性', () => {
        it('项目详情页包含「质量规则」Tab 标签', async () => {
            wrapper = mountDetail({ projectId: 1 })
            await flushPromises()
            expect(wrapper.text()).toContain('质量规则')
        })

        it('同时保留其他 Tab（基本信息/环境配置/文件管理/自愈配置/测试能力）', async () => {
            wrapper = mountDetail({ projectId: 1 })
            await flushPromises()
            const text = wrapper.text()
            expect(text).toContain('基本信息')
            expect(text).toContain('环境配置')
            expect(text).toContain('文件管理')
            expect(text).toContain('自愈配置')
            expect(text).toContain('测试能力')
        })
    })

    describe('SubTask 8.4 - URL tab 参数与重定向', () => {
        it('query.tab=quality-rule 时初始激活质量规则 Tab', async () => {
            wrapper = mountDetail({ projectId: 1, tab: 'quality-rule' })
            await flushPromises()
            // activeTab==='quality-rule' → QualityRuleTab 桩渲染
            expect(wrapper.find('.stub-quality-rule').exists()).toBe(true)
        })

        it('未传 tab 时默认激活「基本信息」', async () => {
            wrapper = mountDetail({ projectId: 1 })
            await flushPromises()
            expect(wrapper.find('.stub-quality-rule').exists()).toBe(false)
        })

        it('非法 tab 值回退到「基本信息」，不激活质量规则', async () => {
            wrapper = mountDetail({ projectId: 1, tab: 'invalid-tab' })
            await flushPromises()
            expect(wrapper.find('.stub-quality-rule').exists()).toBe(false)
        })

        it('/home/system/quality-rule 路由重定向到项目详情 quality-rule Tab', () => {
            const qrRoute = findRouteByPath(routes, 'quality-rule')
            expect(qrRoute).toBeDefined()
            expect(qrRoute?.redirect).toBe('/home/project/detail?tab=quality-rule')
            // 重定向后不再挂载旧组件，避免冗余加载
            expect(qrRoute?.component).toBeUndefined()
        })
    })

    describe('SubTask 8.2 - API 调用携带 project_id', () => {
        it('激活质量规则 Tab 时向 QualityRuleTab 传入正确 projectId', async () => {
            wrapper = mountDetail({ projectId: 7, tab: 'quality-rule' })
            await flushPromises()
            const qrStub = wrapper.find('.stub-quality-rule')
            expect(qrStub.exists()).toBe(true)
            expect(qrStub.attributes('data-project-id')).toBe('7')
        })

        it('QualityRuleTab 直接挂载时按 projectId 调用 getQualityRules', async () => {
            wrapper = mount(QualityRuleTab, { props: { projectId: 123 } })
            await flushPromises()
            expect(getQualityRulesMock).toHaveBeenCalledWith(123)
        })

        it('QualityRuleTab projectId 变化时重新按新 id 调用 API', async () => {
            wrapper = mount(QualityRuleTab, { props: { projectId: 1 } })
            await flushPromises()
            expect(getQualityRulesMock).toHaveBeenCalledWith(1)
            await wrapper.setProps({ projectId: 2 })
            await flushPromises()
            expect(getQualityRulesMock).toHaveBeenCalledWith(2)
        })

        it('端到端：detail 内嵌真实 QualityRuleTab 按 projectId 调用 API', async () => {
            wrapper = mountDetail({ projectId: 9, tab: 'quality-rule', realQualityRule: true })
            // 双轮 flush：① fetchProjectDetail 完成 ② QualityRuleTab 挂载并请求
            await flushPromises()
            await flushPromises()
            expect(getQualityRulesMock).toHaveBeenCalledWith(9)
        })

        it('projectId 为 0 时不发起 API 请求（空值兜底）', async () => {
            wrapper = mount(QualityRuleTab, { props: { projectId: 0 } })
            await flushPromises()
            expect(getQualityRulesMock).not.toHaveBeenCalled()
        })

        it('恢复默认时按 projectId 调用 updateQualityRule', async () => {
            // rule_value(90) ≠ default_value(80) → 「恢复默认」按钮可用
            getQualityRulesMock.mockResolvedValue({
                data: [
                    {
                        rule_key: 'min_pass_rate',
                        rule_value: 90,
                        default_value: 80,
                        description: '通过率门槛',
                        value_type: 'number',
                    },
                ],
            })
            // spyOn 共享模块引用的 ElMessageBox.confirm，使其自动确认
            // MessageBoxData 类型为 MessageBoxInputData & Action（交集为 never），需 cast
            const confirmSpy = vi
                .spyOn(ElMessageBox, 'confirm')
                .mockResolvedValue('confirm' as never)
            wrapper = mount(QualityRuleTab, { props: { projectId: 55 } })
            await flushPromises()
            // 点击「恢复默认」按钮（表格内，渲染正常）
            const resetBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('恢复默认'))
            expect(resetBtn, '应存在恢复默认按钮').toBeTruthy()
            await resetBtn!.trigger('click')
            await flushPromises()
            // 确认后调用 updateQualityRule，第一参数为 projectId
            expect(updateQualityRuleMock).toHaveBeenCalledWith(
                55,
                expect.objectContaining({
                    rule_key: 'min_pass_rate',
                    rule_value: 80,
                })
            )
            confirmSpy.mockRestore()
        })
    })
})

describe('ProjectDetail 测试能力 Tab 迁移（Task 9）', () => {
    let wrapper: VueWrapper | null

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        getTestCapabilitiesMock.mockResolvedValue({ data: [] })
        getQualityRulesMock.mockResolvedValue({ data: [] })
        wrapper = null
    })

    afterEach(() => {
        wrapper?.unmount()
        wrapper = null
        vi.restoreAllMocks()
    })

    describe('SubTask 9.4 - URL tab 参数与路由重定向', () => {
        it('query.tab=test-capability 时初始激活测试能力 Tab', async () => {
            wrapper = mountDetail({ projectId: 1, tab: 'test-capability' })
            await flushPromises()
            expect(wrapper.find('.stub-test-capability').exists()).toBe(true)
        })

        it('/home/system/test-capability 路由重定向到项目详情 test-capability Tab', () => {
            const tcRoute = findRouteByPath(routes, 'test-capability')
            expect(tcRoute).toBeDefined()
            expect(tcRoute?.redirect).toBe('/home/project/detail?tab=test-capability')
            // 重定向后不再挂载旧组件，避免冗余加载
            expect(tcRoute?.component).toBeUndefined()
        })
    })

    describe('SubTask 9.2 - API 调用携带 project_id', () => {
        it('激活测试能力 Tab 时向 TestCapabilityTab 传入正确 projectId', async () => {
            wrapper = mountDetail({ projectId: 7, tab: 'test-capability' })
            await flushPromises()
            const tcStub = wrapper.find('.stub-test-capability')
            expect(tcStub.exists()).toBe(true)
            expect(tcStub.attributes('data-project-id')).toBe('7')
        })

        it('TestCapabilityTab 直接挂载时按 projectId 调用 getList', async () => {
            wrapper = mount(TestCapabilityTab, { props: { projectId: 123 } })
            await flushPromises()
            expect(getTestCapabilitiesMock).toHaveBeenCalledWith({ project_id: 123 })
        })

        it('TestCapabilityTab projectId 变化时重新按新 id 调用 API', async () => {
            wrapper = mount(TestCapabilityTab, { props: { projectId: 1 } })
            await flushPromises()
            expect(getTestCapabilitiesMock).toHaveBeenCalledWith({ project_id: 1 })
            await wrapper.setProps({ projectId: 2 })
            await flushPromises()
            expect(getTestCapabilitiesMock).toHaveBeenCalledWith({ project_id: 2 })
        })

        it('端到端：detail 内嵌真实 TestCapabilityTab 按 projectId 调用 API', async () => {
            wrapper = mountDetail({
                projectId: 9,
                tab: 'test-capability',
                realTestCapability: true,
            })
            // 双轮 flush：① fetchProjectDetail 完成 ② TestCapabilityTab 挂载并请求
            await flushPromises()
            await flushPromises()
            expect(getTestCapabilitiesMock).toHaveBeenCalledWith({ project_id: 9 })
        })

        it('projectId 为 0 时不发起 API 请求（空值兜底）', async () => {
            wrapper = mount(TestCapabilityTab, { props: { projectId: 0 } })
            await flushPromises()
            expect(getTestCapabilitiesMock).not.toHaveBeenCalled()
        })
    })
})
