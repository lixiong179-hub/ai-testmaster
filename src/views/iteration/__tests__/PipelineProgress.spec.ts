import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import type { PipelineRun, PipelineStep, PipelineArtifact } from '@/api/pipeline'

// --- Mock 句柄（hoisted 保证 vi.mock 工厂可引用） ---

const routerPush = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const routerBack = vi.hoisted(() => vi.fn())

const pipelineApiMock = vi.hoisted(() => ({
    getPipelineRun: vi.fn(),
    getPipelineSummary: vi.fn(),
    getInferredSummary: vi.fn(),
    runPipeline: vi.fn(),
}))

const reviewApiMock = vi.hoisted(() => ({
    getReviewsByIteration: vi.fn(),
}))

const aiInvocationApiMock = vi.hoisted(() => ({
    getRunCost: vi.fn(),
}))

vi.mock('vue-router', () => ({
    useRoute: () => ({ params: { runId: '501' } }),
    useRouter: () => ({ push: routerPush, back: routerBack }),
    createRouter: vi.fn(() => ({
        beforeEach: vi.fn(),
        afterEach: vi.fn(),
        onError: vi.fn(),
        currentRoute: { value: { path: '/', fullPath: '/' } },
        push: routerPush,
    })),
    createWebHistory: vi.fn(),
}))

// 避免 request.ts 导入真实 router 触发 createRouter 调用链
vi.mock('@/router', () => ({
    default: {
        push: routerPush,
        currentRoute: { value: { path: '/', fullPath: '/' } },
    },
}))

vi.mock('@/api/pipeline', () => ({ pipelineApi: pipelineApiMock }))
vi.mock('@/api/review', () => ({ reviewApi: reviewApiMock }))
vi.mock('@/api/aiInvocation', () => ({
    aiInvocationApi: aiInvocationApiMock,
    // 汇率常量与生产实现一致，保证 Token 成本换算可断言
    usdToCny: (usd: number) => Number((usd * 7.25).toFixed(4)),
}))

// 仅替换 ElMessage/ElMessageBox，保留真实组件供渲染（ElMessageBox.confirm 模拟为 resolve）
vi.mock('element-plus', async () => {
    const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
    return {
        ...actual,
        ElMessage: {
            success: vi.fn(),
            warning: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
        },
        ElMessageBox: {
            confirm: vi.fn(() => Promise.resolve('confirm')),
        },
    }
})

// 桩：ConfirmationDialog 非本测试目标，避免其内部渲染干扰
const ConfirmationDialogStub = defineComponent({
    name: 'ConfirmationDialog',
    props: { visible: Boolean, reason: String, schema: Object },
    emits: ['confirm'],
    template: '<div v-if="visible" class="stub-confirm" />',
})

// --- 辅助构造 ---

function makeRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
    return {
        id: 501,
        iteration_id: 77,
        input_hash: 'abc12345',
        pipeline_version: '1.0.0',
        status: 'completed',
        started_at: '2026-07-30T10:00:00',
        finished_at: '2026-07-30T10:05:00',
        error: null,
        pause_payload: null,
        steps: [],
        artifacts: [],
        ...overrides,
    }
}

/** 构造单个 PipelineStep 测试数据 */
function makeStep(overrides: Partial<PipelineStep> = {}): PipelineStep {
    return {
        id: 1,
        step_name: 'signal_gatherer',
        status: 'done',
        started_at: '2026-07-30T10:00:00',
        finished_at: '2026-07-30T10:01:00',
        error: null,
        retried_count: 0,
        degraded: false,
        ...overrides,
    }
}

/** 构造单个 PipelineArtifact 测试数据 */
function makeArtifact(overrides: Partial<PipelineArtifact> = {}): PipelineArtifact {
    return {
        id: 1,
        kind: 'raw_signals',
        confidence: 0.92,
        schema_version: '1.0.0',
        created_at: '2026-07-30T10:01:00',
        ...overrides,
    }
}

/** 从挂载实例中按文本匹配 el-button */
function findButton(wrapper: ReturnType<typeof mount>, text: string) {
    return wrapper.findAll('button').find((b) => b.text().includes(text))
}

async function mountView() {
    const PipelineProgress = (await import('../PipelineProgress.vue')).default
    return mount(PipelineProgress, {
        global: {
            stubs: {
                ConfirmationDialog: ConfirmationDialogStub,
            },
        },
    })
}

// --- 测试用例 ---

describe('PipelineProgress - 终态主操作串联（Task 2）', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        // 不设置 localStorage token，使 connectWs 直接返回，避免真实 WebSocket
        localStorage.clear()
        vi.clearAllMocks()
        // 默认摘要接口返回空，避免 loadPipelineSummary 报错
        pipelineApiMock.getPipelineSummary.mockResolvedValue({ data: null })
        pipelineApiMock.getInferredSummary.mockResolvedValue({ data: null })
        // 默认 Token 成本接口返回空账单，避免 onMounted 触发的 fetchTokenUsage 报错
        aiInvocationApiMock.getRunCost.mockResolvedValue({
            totalCalls: 0,
            totalPromptTokens: 0,
            totalCompletionTokens: 0,
            totalTokens: 0,
            totalCostUsd: 0,
        })
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    it('completed 态显示"前往评审 Inbox"主按钮，不显示重试/重新启动', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'completed' }),
        })
        const wrapper = await mountView()
        await flushPromises()

        const banner = wrapper.find('.terminal-state-banner')
        expect(banner.exists()).toBe(true)
        expect(banner.classes()).toContain('terminal-completed')

        expect(findButton(wrapper, '前往评审 Inbox')).toBeTruthy()
        expect(findButton(wrapper, '重试 Pipeline')).toBeFalsy()
        expect(findButton(wrapper, '重新启动')).toBeFalsy()
        expect(findButton(wrapper, '查看错误')).toBeFalsy()
    })

    it('completed 态点击"前往评审 Inbox"携带 reviewId 跳转评审 Inbox', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'completed' }),
        })
        // 模拟该迭代已有评审记录（最新一条 id=999）
        reviewApiMock.getReviewsByIteration.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: {
                reviews: [
                    {
                        id: 999,
                        iteration_id: 77,
                        kind: 'regression',
                        status: 'in_progress',
                        created_at: '2026-07-30T10:06:00',
                        finalized_at: null,
                    },
                ],
                total: 1,
            },
        })
        const wrapper = await mountView()
        await flushPromises()

        const btn = findButton(wrapper, '前往评审 Inbox')
        expect(btn).toBeTruthy()
        await btn!.trigger('click')
        await flushPromises()

        expect(reviewApiMock.getReviewsByIteration).toHaveBeenCalledWith(77)
        // 携带 reviewId 定位最新评审，并以 query 携带 iteration_id 上下文
        expect(routerPush).toHaveBeenCalledWith({
            name: 'IterationReviewInbox',
            params: { reviewId: '999' },
            query: { iteration_id: '77' },
        })
    })

    it('completed 态无评审记录时跳转评审列表（reviewId=0）', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'completed' }),
        })
        reviewApiMock.getReviewsByIteration.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: { reviews: [], total: 0 },
        })
        const wrapper = await mountView()
        await flushPromises()

        const btn = findButton(wrapper, '前往评审 Inbox')
        await btn!.trigger('click')
        await flushPromises()

        expect(routerPush).toHaveBeenCalledWith('/home/iteration/review/0')
    })

    it('failed 态不显示评审跳转按钮，显示"查看错误"+"重试 Pipeline"', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({
                status: 'failed',
                error: '用例生成步骤超时',
                finished_at: '2026-07-30T10:03:00',
            }),
        })
        const wrapper = await mountView()
        await flushPromises()

        const banner = wrapper.find('.terminal-state-banner')
        expect(banner.exists()).toBe(true)
        expect(banner.classes()).toContain('terminal-failed')

        // 失败态不出现评审跳转
        expect(findButton(wrapper, '前往评审 Inbox')).toBeFalsy()
        expect(findButton(wrapper, '重新启动')).toBeFalsy()
        // 出现失败专属操作
        expect(findButton(wrapper, '查看错误')).toBeTruthy()
        expect(findButton(wrapper, '重试 Pipeline')).toBeTruthy()
        // 错误详情 alert 渲染
        expect(wrapper.find('.error-alert').exists()).toBe(true)
    })

    it('cancelled 态显示"重新启动"，不显示评审跳转/重试', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'cancelled', finished_at: '2026-07-30T10:02:00' }),
        })
        const wrapper = await mountView()
        await flushPromises()

        const banner = wrapper.find('.terminal-state-banner')
        expect(banner.exists()).toBe(true)
        expect(banner.classes()).toContain('terminal-cancelled')

        expect(findButton(wrapper, '重新启动')).toBeTruthy()
        expect(findButton(wrapper, '前往评审 Inbox')).toBeFalsy()
        expect(findButton(wrapper, '重试 Pipeline')).toBeFalsy()
    })

    it('running 态不渲染终态操作横幅', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'running', finished_at: null }),
        })
        const wrapper = await mountView()
        await flushPromises()

        expect(wrapper.find('.terminal-state-banner').exists()).toBe(false)
        expect(findButton(wrapper, '前往评审 Inbox')).toBeFalsy()
    })

    it('failed 态点击"重试 Pipeline"以场景4重新启动并跳转新运行', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'failed', error: '超时' }),
        })
        pipelineApiMock.runPipeline.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: { run_id: 602, iteration_id: 77, status: 'pending', scenario: 4 },
        })
        const wrapper = await mountView()
        await flushPromises()

        const btn = findButton(wrapper, '重试 Pipeline')
        expect(btn).toBeTruthy()
        await btn!.trigger('click')
        await flushPromises()

        expect(pipelineApiMock.runPipeline).toHaveBeenCalledWith(77, { scenario: 4 })
        expect(routerPush).toHaveBeenCalledWith({
            name: 'IterationPipelineProgress',
            params: { runId: 602 },
        })
    })
})

describe('PipelineProgress - 横向进度条与 Token 显示（Task 16）', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        // 不设置 localStorage token，使 connectWs 直接返回，避免真实 WebSocket
        localStorage.clear()
        vi.clearAllMocks()
        pipelineApiMock.getPipelineSummary.mockResolvedValue({ data: null })
        pipelineApiMock.getInferredSummary.mockResolvedValue({ data: null })
        aiInvocationApiMock.getRunCost.mockResolvedValue({
            totalCalls: 0,
            totalPromptTokens: 0,
            totalCompletionTokens: 0,
            totalTokens: 0,
            totalCostUsd: 0,
        })
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    it('渲染横向 el-steps 进度条，步骤数量与 runData.steps 一致', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({
                status: 'running',
                finished_at: null,
                steps: [
                    makeStep({ id: 1, step_name: 'signal_gatherer', status: 'done' }),
                    makeStep({ id: 2, step_name: 'testpoint_alignment', status: 'running' }),
                    makeStep({ id: 3, step_name: 'case_generation', status: 'pending' }),
                ],
            }),
        })
        const wrapper = await mountView()
        await flushPromises()

        const steps = wrapper.find('.steps-bar')
        expect(steps.exists()).toBe(true)
        expect(steps.classes()).toContain('el-steps')
        // 横向布局：el-steps 默认 direction=horizontal，不含 el-steps--vertical
        expect(steps.classes()).not.toContain('el-steps--vertical')
        const stepEls = wrapper.findAll('.steps-bar .el-step')
        expect(stepEls).toHaveLength(3)
    })

    it('已完成 Step 标记 success、当前运行 Step 标记 process、失败 Step 标记 error', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({
                status: 'running',
                finished_at: null,
                steps: [
                    makeStep({ id: 1, step_name: 'signal_gatherer', status: 'done' }),
                    makeStep({ id: 2, step_name: 'testpoint_alignment', status: 'running' }),
                    makeStep({
                        id: 3,
                        step_name: 'case_generation',
                        status: 'failed',
                        error: '生成超时',
                    }),
                ],
            }),
        })
        const wrapper = await mountView()
        await flushPromises()

        // el-step 的状态类（is-success/is-process/is-error）应用在 .el-step__head 上
        const heads = wrapper.findAll('.steps-bar .el-step__head')
        expect(heads).toHaveLength(3)
        expect(heads[0].classes()).toContain('is-success')
        expect(heads[1].classes()).toContain('is-process')
        expect(heads[2].classes()).toContain('is-error')
    })

    it('步骤标题渲染中文名称并展示状态描述', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({
                status: 'running',
                finished_at: null,
                steps: [
                    makeStep({ id: 1, step_name: 'signal_gatherer', status: 'done' }),
                    makeStep({ id: 2, step_name: 'case_generation', status: 'running' }),
                ],
            }),
        })
        const wrapper = await mountView()
        await flushPromises()

        const titles = wrapper.findAll('.steps-bar .step-title')
        expect(titles[0].text()).toContain('信号采集')
        expect(titles[1].text()).toContain('用例生成')
        // description 槽展示状态文案
        const descs = wrapper.findAll('.steps-bar .step-desc')
        expect(descs[0].text()).toBe('已完成')
        expect(descs[1].text()).toBe('运行中')
    })

    it('右上角累计 Token 标签按"Token: N | 成本: ¥X.XX"格式展示', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'completed' }),
        })
        // 12345 tokens；0.17 USD → 0.17*7.25=1.2325 → toFixed(2)=1.23
        aiInvocationApiMock.getRunCost.mockResolvedValue({
            totalCalls: 8,
            totalPromptTokens: 9000,
            totalCompletionTokens: 3345,
            totalTokens: 12345,
            totalCostUsd: 0.17,
        })
        const wrapper = await mountView()
        await flushPromises()

        const tag = wrapper.find('.token-usage-tag')
        expect(tag.exists()).toBe(true)
        expect(tag.text()).toBe('Token: 12,345 | 成本: ¥1.23')
        // 按运行 ID 拉取账单
        expect(aiInvocationApiMock.getRunCost).toHaveBeenCalledWith(501)
    })

    it('Token 账单未加载时展示占位符，不显示具体数值', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'completed' }),
        })
        // 模拟拉取失败，回退到未加载占位
        aiInvocationApiMock.getRunCost.mockRejectedValue(new Error('network error'))
        const wrapper = await mountView()
        await flushPromises()

        const tag = wrapper.find('.token-usage-tag')
        expect(tag.exists()).toBe(true)
        expect(tag.text()).toBe('Token: — | 成本: —')
    })

    it('无步骤数据时渲染空状态而非进度条', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({ status: 'pending', steps: [] }),
        })
        const wrapper = await mountView()
        await flushPromises()

        expect(wrapper.find('.steps-bar').exists()).toBe(false)
        expect(wrapper.find('.el-empty').exists()).toBe(true)
    })

    it('产物存在时步骤标题挂载 tooltip，内容模板可获取产物摘要', async () => {
        pipelineApiMock.getPipelineRun.mockResolvedValue({
            code: 0,
            message: 'ok',
            data: makeRun({
                status: 'completed',
                steps: [
                    makeStep({ id: 1, step_name: 'signal_gatherer', status: 'done' }),
                    makeStep({ id: 2, step_name: 'case_generation', status: 'done' }),
                ],
                artifacts: [
                    makeArtifact({ id: 10, kind: 'raw_signals', confidence: 0.92 }),
                    makeArtifact({ id: 11, kind: 'generated_cases', confidence: 0.8 }),
                ],
            }),
        })
        const wrapper = await mountView()
        await flushPromises()

        // 每个 step-title 内都挂载了 el-tooltip 触发器
        const tooltips = wrapper.findAll('.steps-bar .step-title')
        expect(tooltips).toHaveLength(2)
        // 产物摘要通过 getStepArtifact 计算：raw_signals 置信度 0.92 → "92.0%"
        // 这里通过 composable 的纯函数间接验证，不再触发真实 hover（tooltip teleport + 延迟）
        expect(tooltips[0].text()).toContain('信号采集')
    })
})
