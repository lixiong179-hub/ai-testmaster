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
}))

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

describe('useReviewInbox - 评审 Inbox 统计与筛选（Task 14）', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        // 默认 getDecisions 返回空决策 + in_progress 状态（onMounted 不触发，仅兜底）
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

    describe('stats 统计卡片数据计算', () => {
        it('正确统计 total/decided/undecided/conflict', () => {
            const { decisions, stats } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, human_verdict: 'keep' }),
                makeDecision({ id: 2, human_verdict: 'modify' }),
                makeDecision({ id: 3, human_verdict: undefined }),
                makeDecision({ id: 4, human_verdict: undefined, conflict_marker: true }),
            ]
            expect(stats.value).toEqual({ total: 4, decided: 2, undecided: 2, conflict: 1 })
        })

        it('空决策列表时所有统计为 0', () => {
            const { stats } = useReviewInbox()
            expect(stats.value).toEqual({ total: 0, decided: 0, undecided: 0, conflict: 0 })
        })

        it('stats 不受筛选器影响，始终反映整体状态', () => {
            const { decisions, stats, filter } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, human_verdict: 'keep' }),
                makeDecision({ id: 2, human_verdict: undefined, conflict_marker: true }),
            ]
            filter.value = { aiVerdict: 'keep', humanVerdict: '', conflict: 'true' }
            expect(stats.value).toEqual({ total: 2, decided: 1, undecided: 1, conflict: 1 })
        })
    })

    describe('filteredDecisions 筛选器过滤逻辑', () => {
        function seed(): ReviewDecision[] {
            return [
                makeDecision({ id: 1, ai_verdict: 'keep', human_verdict: 'keep', conflict_marker: false }),
                makeDecision({ id: 2, ai_verdict: 'modify', human_verdict: undefined, conflict_marker: false }),
                makeDecision({ id: 3, ai_verdict: 'deprecate', human_verdict: 'deprecate', conflict_marker: true }),
                makeDecision({ id: 4, ai_verdict: 'keep', human_verdict: undefined, conflict_marker: false }),
            ]
        }

        it('无筛选时返回全部，且冲突项优先排序置顶', () => {
            const { decisions, filteredDecisions } = useReviewInbox()
            decisions.value = seed()
            const ids = filteredDecisions.value.map((d) => d.id)
            expect(filteredDecisions.value).toHaveLength(4)
            expect(ids[0]).toBe(3)
        })

        it('按 ai_verdict=keep 筛选', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.aiVerdict = 'keep'
            const ids = filteredDecisions.value.map((d) => d.id)
            expect(ids).toEqual(expect.arrayContaining([1, 4]))
            expect(filteredDecisions.value).toHaveLength(2)
        })

        it('按 human_verdict=keep 筛选', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.humanVerdict = 'keep'
            expect(filteredDecisions.value.map((d) => d.id)).toEqual([1])
        })

        it('按 human_verdict=undecided 筛选未判定项', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.humanVerdict = 'undecided'
            const ids = filteredDecisions.value.map((d) => d.id)
            expect(ids).toEqual(expect.arrayContaining([2, 4]))
            expect(filteredDecisions.value).toHaveLength(2)
        })

        it('按 conflict=true 筛选仅冲突项', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.conflict = 'true'
            expect(filteredDecisions.value.map((d) => d.id)).toEqual([3])
        })

        it('按 conflict=false 筛选非冲突项', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.conflict = 'false'
            expect(filteredDecisions.value.every((d) => !d.conflict_marker)).toBe(true)
            expect(filteredDecisions.value).toHaveLength(3)
        })

        it('组合筛选（ai_verdict=keep + conflict=false）', () => {
            const { decisions, filteredDecisions, filter } = useReviewInbox()
            decisions.value = seed()
            filter.value.aiVerdict = 'keep'
            filter.value.conflict = 'false'
            const ids = filteredDecisions.value.map((d) => d.id)
            expect(ids).toEqual(expect.arrayContaining([1, 4]))
            expect(filteredDecisions.value).toHaveLength(2)
        })

        it('Tab 切换到 keep 与 aiVerdict 筛选叠加', () => {
            const { decisions, filteredDecisions, filter, activeTab } = useReviewInbox()
            decisions.value = seed()
            activeTab.value = 'keep'
            filter.value.humanVerdict = 'keep'
            expect(filteredDecisions.value.map((d) => d.id)).toEqual([1])
        })
    })

    describe('tableRowClass 冲突项标记', () => {
        it('冲突项返回 conflict-row', () => {
            const { tableRowClass } = useReviewInbox()
            const row = makeDecision({ id: 1, conflict_marker: true })
            expect(tableRowClass({ row })).toBe('conflict-row')
        })

        it('非冲突项返回空字符串', () => {
            const { tableRowClass } = useReviewInbox()
            const row = makeDecision({ id: 1, conflict_marker: false })
            expect(tableRowClass({ row })).toBe('')
        })
    })

    describe('resetFilter', () => {
        it('重置所有筛选条件为空', () => {
            const { filter, resetFilter } = useReviewInbox()
            filter.value = { aiVerdict: 'keep', humanVerdict: 'modify', conflict: 'true' }
            resetFilter()
            expect(filter.value).toEqual({ aiVerdict: '', humanVerdict: '', conflict: '' })
        })
    })

    describe('quickFilterConflict（toggle 快速筛选）', () => {
        it('首次点击切入冲突筛选：切到 all tab + conflict=true 且清空其它筛选', () => {
            const { activeTab, filter, quickFilterConflict } = useReviewInbox()
            activeTab.value = 'keep'
            filter.value = { aiVerdict: 'modify', humanVerdict: 'keep', conflict: '' }
            quickFilterConflict()
            expect(activeTab.value).toBe('all')
            expect(filter.value).toEqual({ aiVerdict: '', humanVerdict: '', conflict: 'true' })
        })

        it('再次点击取消冲突筛选（toggle off）：conflict 清空', () => {
            const { filter, quickFilterConflict } = useReviewInbox()
            filter.value = { aiVerdict: '', humanVerdict: '', conflict: 'true' }
            quickFilterConflict()
            expect(filter.value.conflict).toBe('')
        })
    })

    describe('tabs 计数（含冲突 tab）', () => {
        it('各 tab 计数正确', () => {
            const { decisions, tabs } = useReviewInbox()
            decisions.value = [
                makeDecision({ id: 1, ai_verdict: 'keep', conflict_marker: false }),
                makeDecision({ id: 2, ai_verdict: 'keep', conflict_marker: false }),
                makeDecision({ id: 3, ai_verdict: 'modify', conflict_marker: true }),
                makeDecision({ id: 4, ai_verdict: 'deprecate', conflict_marker: false }),
            ]
            const byKey = Object.fromEntries(tabs.value.map((t) => [t.key, t.count]))
            expect(byKey.all).toBe(4)
            expect(byKey.keep).toBe(2)
            expect(byKey.modify).toBe(1)
            expect(byKey.deprecate).toBe(1)
            expect(byKey.conflict).toBe(1)
        })
    })
})
