import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

/**
 * Task4: 内联 NextStepGuideAction 结构，避免直接 import 类型导致
 * vitest 下 NextStepGuide.vue 第二个 <script lang="ts"> 块的 re-export 报错。
 */
interface NextStepGuideAction {
    label: string
    type?: 'primary' | 'success' | 'warning' | 'info' | 'danger'
    size?: 'small' | 'default' | 'large'
    to?: string
    onClick?: () => void
}

// 使用 vi.hoisted 确保 mock 对象在 vi.mock 工厂执行前已初始化
const routerMock = vi.hoisted(() => ({
    push: vi.fn().mockResolvedValue(undefined),
    back: vi.fn(),
}))

const routeMock = vi.hoisted(() => ({
    query: {} as Record<string, unknown>,
}))

vi.mock('vue-router', () => ({
    useRoute: () => routeMock,
    useRouter: () => routerMock,
    // request.ts 间接经由 @/router 调用 createRouter，需补齐避免链式导入报错
    createRouter: vi.fn(() => ({
        beforeEach: vi.fn(),
        afterEach: vi.fn(),
        onError: vi.fn(),
        currentRoute: { value: { path: '/', fullPath: '/' } },
        push: routerMock.push,
    })),
    createWebHistory: vi.fn(),
}))

vi.mock('@/router', () => ({
    default: {
        push: routerMock.push,
        currentRoute: { value: { path: '/', fullPath: '/' } },
    },
}))

const elplusMock = vi.hoisted(() => ({
    ElMessage: {
        success: vi.fn(),
        warning: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
    },
    ElMessageBox: {
        confirm: vi.fn(() => Promise.resolve()),
    },
}))

vi.mock('element-plus', () => ({
    ElMessage: elplusMock.ElMessage,
    ElMessageBox: elplusMock.ElMessageBox,
}))

/**
 * Task4: 智能生成 store mock。
 * 关键字段：currentStep、selectedProjectId、saveResult、saving、previewCases。
 * saveBatch 通过 mockImplementation 在测试用例内动态设置 saveResult，覆盖成功/部分成功/失败三种场景。
 */
const storeMock = vi.hoisted(() => ({
    currentStep: 'preview' as string,
    selectedTask: 'new_feature' as string,
    selectedProjectId: 100 as number | null,
    saving: false,
    saveResult: null as {
        saved_case_ids: number[]
        status: 'saved' | 'partial_saved' | 'failed'
        saved_count: number
        failed_count: number
    } | null,
    saveError: '',
    previewCases: [] as Array<{
        client_id: string
        title: string
        selected_for_save: boolean
        quality_status: string
    }>,
    passedCount: 0,
    warningCount: 0,
    pendingReviewCount: 0,
    rejectedCount: 0,
    selectedForSaveCount: 0,
    coverageSummary: { total: 0, byCategory: {}, byTestPoint: {} },
    generationContext: null,
    generating: false,
    generationProgress: '',
    progressPercent: null as number | null,
    sseTotalCount: 0,
    saveBatch: vi.fn(),
    reset: vi.fn(),
    abortGeneration: vi.fn(),
    recalcQualitySummary: vi.fn(),
    restorePreference: vi.fn(),
    cancelParsePolling: vi.fn(),
    loadUIPrototypeProjects: vi.fn().mockResolvedValue(undefined),
    loadHistoryAssets: vi.fn().mockResolvedValue(undefined),
    handleUIPrototypeProjectChange: vi.fn().mockResolvedValue(undefined),
    removeCase: vi.fn(),
    regenerateSingleCase: vi.fn().mockResolvedValue(undefined),
    uiUploadDialogVisible: false,
    uiPrototypeProjects: [] as unknown[],
    uiScreenDetails: [] as unknown[],
    uiScreenImageUrls: {} as Record<string, string>,
    uiScreenIds: [] as number[],
    uiParsing: false as boolean | string,
    hasUIParseFailure: false,
    hasUIParsePending: false,
    historyAssets: [] as unknown[],
    selectedHistoryAssetIds: [] as number[],
    removeHistoryAsset: vi.fn(),
    historyClassification: null,
    historyItemSelections: new Map<string, boolean>(),
    setHistoryItemSelection: vi.fn(),
    uploadHistoryAsset: vi.fn(),
    importSystemCasesAsHistory: vi.fn(),
    uploadUIScreens: vi.fn(),
    parseUIScreens: vi.fn(),
    toggleUIScreen: vi.fn(),
    testPointIds: [] as number[],
    requirementFileIds: [] as number[],
    uiScreenMatchResults: [] as unknown[],
    warnings: [] as unknown[],
    warningUserTexts: [] as unknown[],
    evidenceRefsDisplay: [] as unknown[],
    materialLevel: 'L3',
    materialLevelText: '完整',
    scenarioType: 'A1_REQUIREMENT_TESTPOINT_UI',
    contextStats: {} as Record<string, unknown>,
    strategyDisplayText: '需求+测试点+UI',
    selectedUIPrototypeProjectId: null as number | null,
    advancedConfig: {
        case_type: 'manual',
        exec_mode: 'manual',
        priority: 2,
        mode: 'linear',
    },
}))

vi.mock('@/store/smartGeneration', () => ({
    useSmartGenerationStore: () => storeMock,
}))

vi.mock('@/store/project', () => ({
    useProjectStore: () => ({ currentProjectId: 100 }),
}))

vi.mock('@/store/smartGenerationHelpers', () => ({
    extractErrorDetail: vi.fn((_e: unknown, fallback?: string) => fallback || '错误'),
}))

vi.mock('@/utils/pagination', () => ({
    extractListData: vi.fn(() => []),
}))

vi.mock('@/utils/request', () => ({
    default: { get: vi.fn().mockResolvedValue({}) },
}))

import SmartGenerate from '../smart-generate.vue'

/** 挂载智能生成组件，stub 直接子组件以隔离渲染 */
function mountComponent() {
    return mount(SmartGenerate, {
        global: {
            stubs: {
                ErrorState: true,
                QualityDonutChart: true,
                PreviewCaseItem: true,
                SmartGenerateDialogs: true,
            },
        },
    })
}

/** 构造保存成功响应（含 saved_case_ids） */
function makeSavedResult(
    savedCaseIds: number[],
    status: 'saved' | 'partial_saved' | 'failed' = 'saved',
) {
    return {
        batch_id: 1,
        idempotency_key: 'k-1',
        save_mode: 'draft',
        saved_count: savedCaseIds.length,
        failed_count: status === 'failed' ? savedCaseIds.length : 0,
        saved_case_ids: savedCaseIds,
        failures: [],
        status,
    }
}

describe('smart-generate - 智能生成保存后 NextStepGuide 引导（Task 4）', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        // 默认进入预览步骤，已选项目，预览列表含 1 条用例
        storeMock.currentStep = 'preview'
        storeMock.selectedTask = 'new_feature'
        storeMock.selectedProjectId = 100
        storeMock.saving = false
        storeMock.saveResult = null
        storeMock.saveError = ''
        storeMock.previewCases = [
            {
                client_id: 'c1',
                title: '用例1',
                selected_for_save: true,
                quality_status: 'passed',
            },
        ]
        storeMock.passedCount = 1
        storeMock.selectedForSaveCount = 1
        // saveBatch 默认模拟成功并写入 saved_case_ids
        storeMock.saveBatch.mockImplementation(async () => {
            storeMock.saveResult = makeSavedResult([101, 102])
        })
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('handleSave', () => {
        it('保存成功后展示 NextStepGuide 引导条', async () => {
            const wrapper = mountComponent()
            await flushPromises()

            // 初始引导条不可见
            expect(wrapper.find('.next-step-guide').exists()).toBe(false)

            // 点击保存按钮触发 handleSave
            const saveBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('保存'))
            expect(saveBtn).toBeTruthy()
            await saveBtn!.trigger('click')
            await flushPromises()

            // 验证 saveBatch 被调用
            expect(storeMock.saveBatch).toHaveBeenCalled()
            // Task4: 引导条显示
            expect(wrapper.find('.next-step-guide').exists()).toBe(true)
            expect(wrapper.find('.guide-title').text()).toBe('用例保存成功')
        })

        it('保存失败（status=failed）时不展示 NextStepGuide 引导条', async () => {
            storeMock.saveBatch.mockImplementation(async () => {
                storeMock.saveResult = makeSavedResult([], 'failed')
            })
            const wrapper = mountComponent()
            await flushPromises()

            const saveBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('保存'))
            await saveBtn!.trigger('click')
            await flushPromises()

            expect(wrapper.find('.next-step-guide').exists()).toBe(false)
        })

        it('部分保存成功（partial_saved）也展示 NextStepGuide 引导条', async () => {
            storeMock.saveBatch.mockImplementation(async () => {
                storeMock.saveResult = makeSavedResult([101], 'partial_saved')
            })
            const wrapper = mountComponent()
            await flushPromises()

            const saveBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('保存'))
            await saveBtn!.trigger('click')
            await flushPromises()

            expect(wrapper.find('.next-step-guide').exists()).toBe(true)
        })
    })

    describe('guideActions - 选项配置', () => {
        async function triggerSaveAndGetMapping() {
            const wrapper = mountComponent()
            await flushPromises()
            const saveBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('保存'))
            await saveBtn!.trigger('click')
            await flushPromises()
            // 读取 NextStepGuide 组件 props.actions
            const guide = wrapper.findComponent({ name: 'NextStepGuide' })
            // 若 stub 渲染失败，回退查找 DOM 中按钮文案
            const actions: NextStepGuideAction[] =
                (guide.props('actions') as NextStepGuideAction[]) ?? []
            return { wrapper, actions }
        }

        it('提供两个选项且文案与类型正确', async () => {
            const { actions } = await triggerSaveAndGetMapping()
            expect(actions).toHaveLength(2)
            expect(actions[0].label).toBe('查看用例列表')
            expect(actions[0].type).toBe('primary')
            expect(actions[1].label).toBe('创建执行任务')
            expect(actions[1].type).toBe('success')
        })

        it('选项1 onClick 跳转用例列表并携带 project_id query', async () => {
            const { actions } = await triggerSaveAndGetMapping()
            actions[0].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'CaseList',
                query: { project_id: '100' },
            })
        })

        it('选项2 onClick 跳转创建任务携带 projectId 参数与 case_ids query', async () => {
            const { actions } = await triggerSaveAndGetMapping()
            actions[1].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'TaskCreate',
                params: { projectId: '100' },
                query: { case_ids: '101,102' },
            })
        })

        it('选项2 在 selectedProjectId 缺失时降级提示且不跳转', async () => {
            const { actions } = await triggerSaveAndGetMapping()
            // mount 后再清空 selectedProjectId，避免 onMounted 中被 projectStore.currentProjectId 回填
            storeMock.selectedProjectId = null
            actions[1].onClick?.()
            expect(elplusMock.ElMessage.warning).toHaveBeenCalled()
            expect(routerMock.push).not.toHaveBeenCalledWith(
                expect.objectContaining({ name: 'TaskCreate' }),
            )
        })

        it('选项2 在 saved_case_ids 为空时仍跳转但不带 case_ids query', async () => {
            storeMock.saveBatch.mockImplementation(async () => {
                storeMock.saveResult = makeSavedResult([])
            })
            const { actions } = await triggerSaveAndGetMapping()
            actions[1].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'TaskCreate',
                params: { projectId: '100' },
                query: {},
            })
        })
    })

    describe('closeSaveGuide', () => {
        it('触发 NextStepGuide close 事件后引导条隐藏', async () => {
            const wrapper = mountComponent()
            await flushPromises()
            const saveBtn = wrapper
                .findAll('button')
                .find((b) => b.text().includes('保存'))
            await saveBtn!.trigger('click')
            await flushPromises()

            expect(wrapper.find('.next-step-guide').exists()).toBe(true)

            // 通过点击 ElAlert 关闭按钮触发 close 链路：
            // ElAlert @close -> NextStepGuide handleClose -> emit('close') -> 父组件 closeSaveGuide
            const closeBtn = wrapper.find('.el-alert__close-btn')
            if (closeBtn.exists()) {
                await closeBtn.trigger('click')
            } else {
                // 兜底：直接向 NextStepGuide 组件 emit close 事件
                wrapper.findComponent({ name: 'NextStepGuide' }).vm.$emit('close')
            }
            await flushPromises()
            await wrapper.vm.$nextTick()
            await flushPromises()

            expect(wrapper.find('.next-step-guide').exists()).toBe(false)
        })
    })
})
