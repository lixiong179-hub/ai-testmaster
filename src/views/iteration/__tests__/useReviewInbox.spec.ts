import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { ReviewDecision } from '@/api/review'

// 用 vi.hoisted 保证 mock 句柄在 vi.mock 工厂执行前已就绪
const routerMock = vi.hoisted(() => ({
    push: vi.fn().mockResolvedValue(undefined),
    back: vi.fn(),
}))

const routeMock = vi.hoisted(() => ({
    params: { reviewId: '123' },
    query: { iteration_id: '456' } as { iteration_id?: string },
}))

const reviewApiMock = vi.hoisted(() => ({
    getDecisions: vi.fn(),
    finalizeReview: vi.fn(),
    decideSingle: vi.fn(),
    decideBatch: vi.fn(),
    undoDecision: vi.fn(),
    rollbackDecision: vi.fn(),
    undoFinalize: vi.fn(),
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

// 避免 request.ts 导入真实 router 触发 createRouter 调用链
vi.mock('@/router', () => ({
    default: {
        push: routerMock.push,
        currentRoute: { value: { path: '/', fullPath: '/' } },
    },
}))

vi.mock('element-plus', () => ({
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

vi.mock('@/api/review', () => ({
    reviewApi: reviewApiMock,
    // 暴露类型供 import type 使用（运行时为空对象不影响）
}))

import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/store/project'
import { useReviewInbox } from '../useReviewInbox'

/** 构造最小可用 ReviewDecision 测试数据 */
function makeDecision(over: Partial<ReviewDecision>): ReviewDecision {
    return {
        id: over.id ?? 1,
        target_kind: over.target_kind ?? 'case',
        target_id: over.target_id ?? 1,
        conflict_marker: over.conflict_marker ?? false,
        accepted_low_confidence: over.accepted_low_confidence ?? false,
        ...over,
    }
}

/** 微任务 flush：等待 ElMessageBox.confirm().then() 链路落地 */
function flushPromises(): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, 0))
}

describe('useReviewInbox - 评审最终化引导（Task 3）', () => {
    let projectStore: ReturnType<typeof useProjectStore>

    beforeEach(() => {
        setActivePinia(createPinia())
        projectStore = useProjectStore()
        projectStore.currentProjectId = 100
        vi.clearAllMocks()
        // 默认 getDecisions 返回空决策 + in_progress 状态
        reviewApiMock.getDecisions.mockResolvedValue({
            data: {
                decisions: [],
                total: 0,
                review: {
                    status: 'in_progress',
                    finalized_at: null,
                    finalized_by: null,
                    undo_window_expires_at: null,
                },
            },
        })
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('handleFinalize', () => {
        it('最终化成功后显示 NextStepGuide 引导', async () => {
            reviewApiMock.finalizeReview.mockResolvedValue({
                data: {
                    review_id: 123,
                    status: 'finalized',
                    finalized_at: '2026-07-30T10:00:00',
                    finalized_by: 1,
                },
            })
            const { handleFinalize, showFinalizeGuide } = useReviewInbox()
            handleFinalize()
            await flushPromises()
            expect(reviewApiMock.finalizeReview).toHaveBeenCalledWith(123)
            expect(showFinalizeGuide.value).toBe(true)
        })

        it('最终化失败时不显示引导', async () => {
            reviewApiMock.finalizeReview.mockRejectedValue({
                response: { status: 400, data: { msg: 'bad' } },
            })
            const { handleFinalize, showFinalizeGuide } = useReviewInbox()
            handleFinalize()
            await flushPromises()
            expect(showFinalizeGuide.value).toBe(false)
        })
    })

    describe('approvedCaseIds', () => {
        it('只收集 final_verdict 为 keep/modify 且 target_kind=case 的 target_id', () => {
            const { decisions, approvedCaseIds } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'keep' }),
                makeDecision({ id: 2, target_kind: 'case', target_id: 102, final_verdict: 'modify' }),
                makeDecision({ id: 3, target_kind: 'case', target_id: 103, final_verdict: 'deprecate' }),
                makeDecision({ id: 4, target_kind: 'requirement', target_id: 201, final_verdict: 'keep' }),
                makeDecision({ id: 5, target_kind: 'case', target_id: 104, final_verdict: undefined }),
            ]
            expect(approvedCaseIds.value).toEqual([101, 102])
        })

        it('无通过用例时返回空数组', () => {
            const { decisions, approvedCaseIds } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'deprecate' }),
            ]
            expect(approvedCaseIds.value).toEqual([])
        })
    })

    describe('guideToCaseList', () => {
        it('跳转用例列表并携带 iteration_id query', () => {
            const { guideToCaseList, showFinalizeGuide } = useReviewInbox()
            showFinalizeGuide.value = true
            guideToCaseList()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'CaseList',
                query: { iteration_id: '456' },
            })
            expect(showFinalizeGuide.value).toBe(false)
        })

        it('iteration_id 缺失时不带该 query 参数', () => {
            const original = routeMock.query.iteration_id
            delete routeMock.query.iteration_id
            const { guideToCaseList } = useReviewInbox()
            guideToCaseList()
            expect(routerMock.push).toHaveBeenCalledWith({ name: 'CaseList', query: {} })
            routeMock.query.iteration_id = original
        })
    })

    describe('guideToTaskCenter', () => {
        it('跳转创建任务携带 project_id 路径参数与 case_ids query', () => {
            const { guideToTaskCenter, decisions } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'keep' }),
                makeDecision({ id: 2, target_kind: 'case', target_id: 102, final_verdict: 'modify' }),
                makeDecision({ id: 3, target_kind: 'case', target_id: 103, final_verdict: 'deprecate' }),
            ]
            guideToTaskCenter()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'TaskCreate',
                params: { projectId: '100' },
                query: { case_ids: '101,102' },
            })
        })

        it('currentProjectId 缺失时降级提示且不跳转', () => {
            projectStore.currentProjectId = null
            const { guideToTaskCenter, decisions } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'keep' }),
            ]
            guideToTaskCenter()
            expect(ElMessage.warning).toHaveBeenCalled()
            expect(routerMock.push).not.toHaveBeenCalled()
        })

        it('approvedCaseIds 为空时降级提示且不跳转', () => {
            const { guideToTaskCenter, decisions } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'deprecate' }),
            ]
            guideToTaskCenter()
            expect(ElMessage.warning).toHaveBeenCalled()
            expect(routerMock.push).not.toHaveBeenCalled()
        })
    })

    describe('guideToIterationList', () => {
        it('跳转到迭代列表', () => {
            const { guideToIterationList, showFinalizeGuide } = useReviewInbox()
            showFinalizeGuide.value = true
            guideToIterationList()
            expect(routerMock.push).toHaveBeenCalledWith({ name: 'IterationList' })
            expect(showFinalizeGuide.value).toBe(false)
        })
    })

    describe('guideActions（NextStepGuide 选项配置）', () => {
        it('提供三个选项且文案与类型正确', () => {
            const { guideActions } = useReviewInbox()
            expect(guideActions.value).toHaveLength(3)
            const labels = guideActions.value.map((a) => a.label)
            expect(labels).toEqual(['查看用例列表', '创建执行任务', '返回迭代列表'])
            expect(guideActions.value[0].type).toBe('primary')
            expect(guideActions.value[1].type).toBe('success')
            expect(guideActions.value[2].type).toBe('info')
        })

        it('选项1 onClick 触发跳转用例列表', () => {
            const { guideActions } = useReviewInbox()
            guideActions.value[0].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'CaseList',
                query: { iteration_id: '456' },
            })
        })

        it('选项2 onClick 触发跳转创建任务（含 case_ids）', () => {
            const { guideActions, decisions } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, target_kind: 'case', target_id: 101, final_verdict: 'keep' }),
                makeDecision({ id: 2, target_kind: 'case', target_id: 102, final_verdict: 'modify' }),
            ]
            guideActions.value[1].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({
                name: 'TaskCreate',
                params: { projectId: '100' },
                query: { case_ids: '101,102' },
            })
        })

        it('选项3 onClick 触发跳转迭代列表', () => {
            const { guideActions } = useReviewInbox()
            guideActions.value[2].onClick?.()
            expect(routerMock.push).toHaveBeenCalledWith({ name: 'IterationList' })
        })
    })

    describe('closeFinalizeGuide', () => {
        it('关闭引导后 visible 为 false', () => {
            const { closeFinalizeGuide, showFinalizeGuide } = useReviewInbox()
            showFinalizeGuide.value = true
            closeFinalizeGuide()
            expect(showFinalizeGuide.value).toBe(false)
        })
    })
})
