import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import QuickProgressView from '../components/QuickProgressView.vue'
import { useQuickTestStore } from '@/store/quickTest'

function mountView(props: { wsConnected?: boolean } = {}) {
    return mount(QuickProgressView, { props })
}

describe('QuickProgressView', () => {
    let store: ReturnType<typeof useQuickTestStore>

    beforeEach(() => {
        localStorage.clear()
        setActivePinia(createPinia())
        store = useQuickTestStore()
        // 模拟 running 态并初始化基础字段
        store.phase = 'running'
        store.taskId = 101
        store.lastUrl = 'https://example.com'
        store.progress = 45
        store.estimatedDurationSec = 300
        store.startedAt = new Date(Date.now() - 60_000).toISOString()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('4 阶段渲染', () => {
        it('渲染 4 个阶段条目且按 spec UX 顺序', () => {
            const wrapper = mountView()
            const items = wrapper.findAll('.stage-item')
            expect(items).toHaveLength(4)
            const labels = items.map((i) => i.find('.stage-label').text())
            expect(labels).toEqual(['站点探索', '用例生成', '任务执行', '报告生成'])
        })

        it('site_exploring 阶段激活站点探索项', () => {
            store.currentStage = 'site_exploring'
            const wrapper = mountView()
            const items = wrapper.findAll('.stage-item')
            expect(items[0].classes()).toContain('is-active')
            expect(items[1].classes()).toContain('is-pending')
        })

        it('case_generating 阶段激活用例生成项且站点探索已完成', () => {
            store.currentStage = 'case_generating'
            const wrapper = mountView()
            const items = wrapper.findAll('.stage-item')
            expect(items[0].classes()).toContain('is-done')
            expect(items[1].classes()).toContain('is-active')
        })

        it('task_assembling 与 executing 都激活任务执行项', () => {
            for (const stage of ['task_assembling', 'executing'] as const) {
                store.currentStage = stage
                const wrapper = mountView()
                const items = wrapper.findAll('.stage-item')
                expect(items[2].classes()).toContain('is-active')
                expect(items[0].classes()).toContain('is-done')
            }
        })

        it('completed 阶段激活报告生成项且全部完成', () => {
            store.currentStage = 'completed'
            store.phase = 'completed'
            store.progress = 100
            const wrapper = mountView()
            const items = wrapper.findAll('.stage-item')
            expect(items[3].classes()).toContain('is-active')
        })
    })

    describe('stage→中文标签映射（spec 偏离①）', () => {
        it('current_stage=site_exploring 渲染「站点探索」', () => {
            store.currentStage = 'site_exploring'
            const wrapper = mountView()
            expect(wrapper.find('.card-subtitle').text()).toContain('站点探索')
        })

        it('current_stage=case_generating 渲染「用例生成」', () => {
            store.currentStage = 'case_generating'
            const wrapper = mountView()
            expect(wrapper.find('.card-subtitle').text()).toContain('用例生成')
        })

        it('current_stage=task_assembling 合并映射为「任务执行」', () => {
            store.currentStage = 'task_assembling'
            const wrapper = mountView()
            expect(wrapper.find('.card-subtitle').text()).toContain('任务执行')
        })

        it('current_stage=completed 映射为「报告生成」', () => {
            store.currentStage = 'completed'
            store.phase = 'completed'
            const wrapper = mountView()
            expect(wrapper.find('.card-subtitle').text()).toContain('报告生成')
        })

        it('current_stage=failed 映射为「执行失败」', () => {
            store.currentStage = 'failed'
            store.phase = 'failed'
            store.errorMessage = 'AI 服务超时'
            const wrapper = mountView()
            expect(wrapper.find('.card-subtitle').text()).toContain('执行失败')
        })
    })

    describe('进度条状态', () => {
        it('phase=failed 时进度条 status=exception', () => {
            store.phase = 'failed'
            store.currentStage = 'failed'
            const wrapper = mountView()
            const progress = wrapper.findComponent({ name: 'ElProgress' })
            expect(progress.props('status')).toBe('exception')
        })

        it('phase=completed 时进度条 status=success', () => {
            store.phase = 'completed'
            store.currentStage = 'completed'
            store.progress = 100
            const wrapper = mountView()
            const progress = wrapper.findComponent({ name: 'ElProgress' })
            expect(progress.props('status')).toBe('success')
        })

        it('phase=running 时进度条 status 为空', () => {
            store.phase = 'running'
            const wrapper = mountView()
            const progress = wrapper.findComponent({ name: 'ElProgress' })
            expect(progress.props('status')).toBe('')
        })
    })

    describe('已用时长与预计剩余', () => {
        it('展示已用时长文案', () => {
            const wrapper = mountView()
            const items = wrapper.findAll('.meta-item')
            const elapsedItem = items.find((i) => i.find('.meta-label').text() === '已用时长')
            expect(elapsedItem).toBeTruthy()
            const value = elapsedItem!.find('.meta-value').text()
            expect(value).toMatch(/分|秒/)
        })

        it('estimatedDurationSec 缺失时预计剩余显示「未知」', () => {
            store.estimatedDurationSec = null
            const wrapper = mountView()
            const items = wrapper.findAll('.meta-item')
            const remainItem = items.find((i) => i.find('.meta-label').text() === '预计剩余')
            const value = remainItem!.find('.meta-value').text()
            expect(value).toBe('未知')
        })

        it('展示网址与任务ID', () => {
            const wrapper = mountView()
            const values = wrapper.findAll('.meta-value').map((v) => v.text())
            expect(values.some((v) => v.includes('https://example.com'))).toBe(true)
            expect(values.some((v) => v.includes('101'))).toBe(true)
        })
    })

    describe('WS 连接状态标签', () => {
        it('wsConnected=true 渲染「实时」成功标签', () => {
            const wrapper = mountView({ wsConnected: true })
            const tags = wrapper.findAll('.ws-tag')
            expect(tags.length).toBeGreaterThan(0)
            expect(tags[0].text()).toBe('实时')
        })

        it('wsConnected=false 渲染「重连中」警告标签', () => {
            const wrapper = mountView({ wsConnected: false })
            const tags = wrapper.findAll('.ws-tag')
            expect(tags.length).toBeGreaterThan(0)
            expect(tags[0].text()).toBe('重连中')
        })
    })

    describe('取消按钮', () => {
        it('点击取消按钮触发 cancel 事件', async () => {
            const wrapper = mountView()
            await wrapper.find('button').trigger('click')
            expect(wrapper.emitted('cancel')).toBeTruthy()
            expect(wrapper.emitted('cancel')).toHaveLength(1)
        })
    })
})
