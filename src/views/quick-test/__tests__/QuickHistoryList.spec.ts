import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import QuickHistoryList from '../components/QuickHistoryList.vue'
import { useQuickTestStore } from '@/store/quickTest'
import type { QuickTestStatusResponse } from '@/api/quickTest'
import type { ApiResponse } from '@/utils/request'

vi.mock('@/api/quickTest', () => {
    const getStatus = vi.fn()
    return {
        default: { getStatus },
        QuickTestApi: { getStatus },
    }
})

import quickTestApi from '@/api/quickTest'

function makeStatusResponse(
    overrides: Partial<QuickTestStatusResponse> = {}
): ApiResponse<QuickTestStatusResponse> {
    return {
        code: 0,
        msg: 'ok',
        message: 'ok',
        data: {
            task_id: 101,
            status: '执行完成',
            progress: 100,
            current_stage: 'completed',
            case_count: 5,
            started_at: '2026-06-27T10:00:00',
            websocket_channel: 'quick_test:101',
            ...overrides,
        },
    }
}

function mountList() {
    return mount(QuickHistoryList)
}

describe('QuickHistoryList', () => {
    let store: ReturnType<typeof useQuickTestStore>

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useQuickTestStore()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('空态渲染', () => {
        it('taskId 缺失时展示空态与提示文案', async () => {
            store.taskId = null
            const wrapper = mountList()
            await flushPromises()
            expect(wrapper.find('.el-empty').exists()).toBe(true)
            expect(wrapper.find('.empty-hint').text()).toContain('发起一次快速测试')
            expect(quickTestApi.getStatus).not.toHaveBeenCalled()
        })

        it('渲染卡片标题与「即将上线」副标题（spec 偏离②）', async () => {
            store.taskId = null
            const wrapper = mountList()
            await flushPromises()
            expect(wrapper.find('.card-title').text()).toBe('历史记录')
            expect(wrapper.find('.card-subtitle').text()).toContain('完整历史记录功能即将上线')
        })
    })

    describe('列表渲染（当前会话记录）', () => {
        it('拉取成功后展示一条记录且字段映射正确', async () => {
            store.taskId = 101
            store.lastUrl = 'https://example.com'
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({
                    status: '执行完成',
                    progress: 100,
                    case_count: 5,
                    started_at: '2026-06-27T10:00:00',
                })
            )
            const wrapper = mountList()
            await flushPromises()
            expect(quickTestApi.getStatus).toHaveBeenCalledWith(101)
            const rows = wrapper.findAll('.el-table__row')
            expect(rows.length).toBeGreaterThanOrEqual(1)
            // 网址列展示 lastUrl
            expect(wrapper.find('.history-url').text()).toContain('https://example.com')
        })

        it('执行完成状态渲染 success 标签', async () => {
            store.taskId = 101
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '执行完成' })
            )
            const wrapper = mountList()
            await flushPromises()
            const tag = wrapper.find('.el-table .el-tag')
            expect(tag.classes().join(' ')).toMatch(/success/)
            expect(tag.text()).toBe('执行完成')
        })

        it('执行失败状态渲染 danger 标签', async () => {
            store.taskId = 101
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '执行失败', current_stage: 'failed' })
            )
            const wrapper = mountList()
            await flushPromises()
            const tag = wrapper.find('.el-table .el-tag')
            expect(tag.classes().join(' ')).toMatch(/danger/)
        })

        it('已停止状态渲染 info 标签', async () => {
            store.taskId = 101
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '已停止', current_stage: 'stopped' })
            )
            const wrapper = mountList()
            await flushPromises()
            const tag = wrapper.find('.el-table .el-tag')
            expect(tag.classes().join(' ')).toMatch(/info/)
        })
    })

    describe('API 失败降级（spec 偏离②）', () => {
        it('getStatus 异常时降级用 store 字段渲染一条记录', async () => {
            store.taskId = 101
            store.lastUrl = 'https://fallback.example.com'
            store.startedAt = '2026-06-27T11:00:00'
            store.caseCount = 3
            store.progress = 50
            store.phase = 'running'
            vi.mocked(quickTestApi.getStatus).mockRejectedValueOnce(new Error('网络错误'))
            const wrapper = mountList()
            await flushPromises()
            // 降级后仍应渲染一行
            const rows = wrapper.findAll('.el-table__row')
            expect(rows.length).toBeGreaterThanOrEqual(1)
            expect(wrapper.find('.history-url').text()).toContain('https://fallback.example.com')
        })

        it('API 失败且 store.phase=failed 时降级状态文案为「执行失败」', async () => {
            store.taskId = 101
            store.phase = 'failed'
            store.lastUrl = 'https://x.example.com'
            vi.mocked(quickTestApi.getStatus).mockRejectedValueOnce(new Error('500'))
            const wrapper = mountList()
            await flushPromises()
            const tag = wrapper.find('.el-table .el-tag')
            expect(tag.text()).toBe('执行失败')
        })
    })

    describe('重看结果 emit', () => {
        it('点击「重看结果」触发 view 事件携带 taskId', async () => {
            store.taskId = 101
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ task_id: 101 })
            )
            const wrapper = mountList()
            await flushPromises()
            const buttons = wrapper.findAll('button')
            const viewBtn = buttons.find((b) => b.text().includes('重看结果'))
            await viewBtn!.trigger('click')
            expect(wrapper.emitted('view')).toBeTruthy()
            expect(wrapper.emitted('view')![0]).toEqual([101])
        })
    })

    describe('再次执行 emit', () => {
        it('点击「再次执行」触发 rerun 事件携带原 URL', async () => {
            store.taskId = 101
            store.lastUrl = 'https://rerun.example.com'
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ task_id: 101 })
            )
            const wrapper = mountList()
            await flushPromises()
            const buttons = wrapper.findAll('button')
            const rerunBtn = buttons.find((b) => b.text().includes('再次执行'))
            await rerunBtn!.trigger('click')
            expect(wrapper.emitted('rerun')).toBeTruthy()
            expect(wrapper.emitted('rerun')![0]).toEqual(['https://rerun.example.com'])
        })
    })
})
