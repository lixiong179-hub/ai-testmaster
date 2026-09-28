import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import type { Iteration } from '@/api/iteration'
import type { Project } from '@/api/project'

// 使用 vi.hoisted 确保 mock 对象在 vi.mock 工厂执行前已初始化
const { mockRouter, mockIterationApi, mockFileApi, mockUiPrototypeApi, mockReviewApi } =
    vi.hoisted(() => ({
        mockRouter: { push: vi.fn() },
        mockIterationApi: {
            getIterations: vi.fn(),
            finalizeIteration: vi.fn(),
            archiveIteration: vi.fn(),
            runPipeline: vi.fn(),
            deleteIteration: vi.fn(),
            createIteration: vi.fn(),
            updateIteration: vi.fn(),
            getIteration: vi.fn(),
            addIterationInput: vi.fn(),
        },
        mockFileApi: { getFileList: vi.fn() },
        mockUiPrototypeApi: { getUIPrototypeProjectList: vi.fn() },
        mockReviewApi: { getReviewsByIteration: vi.fn() },
    }))

vi.mock('vue-router', async () => {
    const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
    return {
        ...actual,
        useRouter: () => mockRouter,
        useRoute: () => ({ params: {}, query: {} }),
    }
})

vi.mock('@/api/iteration', () => ({
    iterationApi: mockIterationApi,
    default: mockIterationApi,
    IterationAPI: mockIterationApi,
    finalizeIteration: vi.fn(),
    runPipeline: vi.fn(),
    archiveIteration: vi.fn(),
}))

vi.mock('@/api/file', () => ({
    fileApi: mockFileApi,
    FileAPI: mockFileApi,
}))

vi.mock('@/api/uiPrototype', () => ({
    uiPrototypeApi: mockUiPrototypeApi,
}))

vi.mock('@/api/review', () => ({
    reviewApi: mockReviewApi,
}))

import IterationList from '../IterationList.vue'
import { useProjectStore } from '@/store/project'
import { getAvailableActions } from '../useIterationList'

const TEST_PROJECT_ID = 10

function makeProject(): Project {
    return {
        id: TEST_PROJECT_ID,
        name: '测试项目',
        description: '',
        project_type: 'web',
        status: 1,
        create_time: '2026-01-01T00:00:00',
        update_time: '2026-01-01T00:00:00',
    }
}

/** 构造覆盖全部状态的测试迭代列表 */
function makeIterations(): Iteration[] {
    return [
        {
            id: 1,
            project_id: TEST_PROJECT_ID,
            name: '草稿迭代',
            version: 'v1.0',
            status: 'draft',
            description: '草稿描述',
            create_time: '2026-01-01T00:00:00',
            update_time: '2026-01-01T00:00:00',
        },
        {
            id: 2,
            project_id: TEST_PROJECT_ID,
            name: '运行中迭代',
            version: 'v2.0',
            status: 'in_pipeline',
            create_time: '2026-02-01T00:00:00',
            update_time: '2026-02-01T00:00:00',
        },
        {
            id: 3,
            project_id: TEST_PROJECT_ID,
            name: '评审中迭代',
            version: 'v3.0',
            status: 'in_review',
            create_time: '2026-03-01T00:00:00',
            update_time: '2026-03-01T00:00:00',
        },
        {
            id: 4,
            project_id: TEST_PROJECT_ID,
            name: '已定稿迭代',
            version: 'v4.0',
            status: 'finalized',
            create_time: '2026-04-01T00:00:00',
            update_time: '2026-04-01T00:00:00',
        },
        {
            id: 5,
            project_id: TEST_PROJECT_ID,
            name: '已归档迭代',
            version: 'v5.0',
            status: 'archived',
            create_time: '2026-05-01T00:00:00',
            update_time: '2026-05-01T00:00:00',
        },
    ]
}

function mockListResponse(items: Iteration[]) {
    return {
        code: 0,
        message: 'ok',
        data: { items, total: items.length, page: 1, page_size: 100 },
    }
}

function mockEmptyStatsResponse() {
    return { code: 0, data: { items: [], total: 0 } }
}

function setupStore(): void {
    const projectStore = useProjectStore()
    projectStore.projects = [makeProject()]
    projectStore.currentProjectId = TEST_PROJECT_ID
}

function mountList() {
    return mount(IterationList)
}

describe('IterationList', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
        setupStore()
        mockIterationApi.getIterations.mockResolvedValue(mockListResponse(makeIterations()))
        mockFileApi.getFileList.mockResolvedValue(mockEmptyStatsResponse())
        mockUiPrototypeApi.getUIPrototypeProjectList.mockResolvedValue(mockEmptyStatsResponse())
        mockReviewApi.getReviewsByIteration.mockResolvedValue({
            code: 0,
            data: { reviews: [], total: 0 },
        })
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('列表展示', () => {
        it('加载并展示全部迭代（5 条覆盖 5 种状态）', async () => {
            const wrapper = mountList()
            await flushPromises()

            expect(mockIterationApi.getIterations).toHaveBeenCalledWith(TEST_PROJECT_ID)
            const rows = wrapper.findAll('.el-table__row')
            expect(rows).toHaveLength(5)
            // 验证迭代名称渲染
            expect(wrapper.find('.iter-name').text()).toBe('草稿迭代')
        })

        it('未选择项目时展示空态提示', async () => {
            const projectStore = useProjectStore()
            projectStore.currentProjectId = null
            const wrapper = mountList()
            await flushPromises()

            expect(wrapper.find('.empty-title').text()).toBe('请先选择项目')
            expect(mockIterationApi.getIterations).not.toHaveBeenCalled()
        })

        it('加载失败时降级为空列表（不抛错）', async () => {
            mockIterationApi.getIterations.mockRejectedValueOnce(new Error('网络错误'))
            const wrapper = mountList()
            await flushPromises()

            // 降级后展示空态（项目已选但无数据）
            expect(wrapper.find('.empty-title').text()).toContain('该项目暂无迭代')
        })
    })

    describe('状态筛选', () => {
        it('筛选 draft 状态后仅展示 1 条草稿迭代', async () => {
            const wrapper = mountList()
            await flushPromises()

            expect(wrapper.findAll('.el-table__row')).toHaveLength(5)

            // 定位状态筛选下拉（带 status-select 类）
            const selects = wrapper.findAllComponents({ name: 'ElSelect' })
            const statusSelect = selects.find((s) => s.classes().includes('status-select'))
            expect(statusSelect).toBeTruthy()
            await statusSelect!.vm.$emit('update:modelValue', 'draft')
            await flushPromises()

            const rows = wrapper.findAll('.el-table__row')
            expect(rows).toHaveLength(1)
            expect(wrapper.find('.iter-name').text()).toBe('草稿迭代')
        })

        it('切换不同状态筛选展示对应迭代，清空后恢复全部', async () => {
            const wrapper = mountList()
            await flushPromises()

            const selects = wrapper.findAllComponents({ name: 'ElSelect' })
            const statusSelect = selects.find((s) => s.classes().includes('status-select'))
            expect(statusSelect).toBeTruthy()

            // 筛选 finalized
            await statusSelect!.vm.$emit('update:modelValue', 'finalized')
            await flushPromises()
            expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
            expect(wrapper.find('.iter-name').text()).toBe('已定稿迭代')

            // 清空筛选恢复全部
            await statusSelect!.vm.$emit('update:modelValue', '')
            await flushPromises()
            expect(wrapper.findAll('.el-table__row')).toHaveLength(5)
        })

        it('筛选无匹配状态时展示空态文案', async () => {
            const wrapper = mountList()
            await flushPromises()

            const selects = wrapper.findAllComponents({ name: 'ElSelect' })
            const statusSelect = selects.find((s) => s.classes().includes('status-select'))
            await statusSelect!.vm.$emit('update:modelValue', 'archived')
            await flushPromises()

            expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
            // 切换为无匹配的 finalized 之外的状态后再次验证
            await statusSelect!.vm.$emit('update:modelValue', 'in_review')
            await flushPromises()
            expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
        })
    })

    describe('操作菜单状态机', () => {
        it.each([
            ['draft', ['run_pipeline', 'edit', 'view_resources', 'delete']],
            ['in_pipeline', ['view_pipeline', 'view_resources']],
            ['in_review', ['finalize', 'view_review', 'view_resources']],
            ['finalized', ['archive', 'view_cases', 'view_resources']],
            ['archived', ['view_cases', 'view_resources']],
        ])('%s 状态返回正确操作集', (status, expected) => {
            const actions = getAvailableActions(status)
            expect(actions.map((a) => a.command)).toEqual(expected)
        })

        it('draft 状态操作标签文案正确', () => {
            const actions = getAvailableActions('draft')
            expect(actions.map((a) => a.label)).toEqual([
                '启动 Pipeline',
                '编辑',
                '查看资源',
                '删除',
            ])
        })

        it('删除操作前加分隔线，其他操作不加', () => {
            const draftActions = getAvailableActions('draft')
            const deleteAction = draftActions.find((a) => a.command === 'delete')
            const runAction = draftActions.find((a) => a.command === 'run_pipeline')
            expect(deleteAction?.divided).toBe(true)
            expect(runAction?.divided).toBe(false)
        })

        it('未知状态回退为仅查看用例（只读）', () => {
            const actions = getAvailableActions('unknown_status')
            expect(actions.map((a) => a.command)).toEqual(['view_cases'])
        })

        it('archived 状态仅显示只读操作（查看用例+查看资源，无写操作）', () => {
            const actions = getAvailableActions('archived')
            expect(actions).toHaveLength(2)
            const commands = actions.map((a) => a.command)
            expect(commands).toContain('view_cases')
            expect(commands).toContain('view_resources')
            // 确保不包含任何写操作
            expect(commands).not.toContain('delete')
            expect(commands).not.toContain('edit')
            expect(commands).not.toContain('run_pipeline')
            expect(commands).not.toContain('finalize')
            expect(commands).not.toContain('archive')
        })

        it('表格每行渲染操作下拉（5 行 5 个 el-dropdown）', async () => {
            const wrapper = mountList()
            await flushPromises()

            const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
            expect(dropdowns).toHaveLength(5)
        })

        it('点击"查看资源"操作跳转资源中心并携带迭代上下文', async () => {
            const wrapper = mountList()
            await flushPromises()

            const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
            // 触发第一行（draft 迭代，id=1, project_id=10）的 view_resources 命令
            await dropdowns[0].vm.$emit('command', 'view_resources')
            await flushPromises()

            expect(mockRouter.push).toHaveBeenCalledWith({
                name: 'RequirementResource',
                query: {
                    project_id: '10',
                    iteration_id: '1',
                },
            })
        })
    })
})
