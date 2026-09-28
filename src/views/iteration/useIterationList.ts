/**
 * 迭代列表页 composable
 *
 * 集中管理迭代列表的分页、状态筛选与状态机驱动的操作菜单逻辑，
 * 保持 IterationList.vue 仅负责视图渲染。复用 useIterationManager（数据/表单）
 * 与 usePagination（分页状态）。
 *
 * 状态机映射（操作菜单按状态动态显示）：
 *   draft       → 启动 Pipeline / 编辑 / 删除
 *   in_pipeline → 查看 Pipeline 进度
 *   in_review   → 定稿 / 查看评审
 *   finalized   → 归档 / 查看用例
 *   archived    → 查看用例（只读）
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/project'
import { useIterationManager } from '@/composables/useIterationManager'
import { usePagination } from '@/composables/usePagination'
import {
    finalizeIteration,
    runPipeline,
    archiveIteration,
    type Iteration,
} from '@/api/iteration'
import { reviewApi } from '@/api/review'
import { ITERATION_STATUS_OPTIONS } from '@/constants/resource'
import type { TagType } from '@/types/element-plus'

/** 迭代操作类型（状态机驱动） */
export type IterationAction =
    | 'run_pipeline'
    | 'edit'
    | 'delete'
    | 'view_pipeline'
    | 'finalize'
    | 'view_review'
    | 'archive'
    | 'view_cases'
    | 'view_resources'

/** 操作菜单项 */
export interface IterationActionItem {
    command: IterationAction
    label: string
    divided?: boolean
}

/** 状态 → 可用操作 映射（状态机） */
const STATUS_ACTION_MAP: Record<string, IterationAction[]> = {
    draft: ['run_pipeline', 'edit', 'view_resources', 'delete'],
    in_pipeline: ['view_pipeline', 'view_resources'],
    in_review: ['finalize', 'view_review', 'view_resources'],
    finalized: ['archive', 'view_cases', 'view_resources'],
    archived: ['view_cases', 'view_resources'],
}

const ACTION_LABELS: Record<IterationAction, string> = {
    run_pipeline: '启动 Pipeline',
    edit: '编辑',
    delete: '删除',
    view_pipeline: '查看 Pipeline 进度',
    finalize: '定稿',
    view_review: '查看评审',
    archive: '归档',
    view_cases: '查看用例',
    view_resources: '查看资源',
}

// 危险操作前加分隔线
const DIVIDED_ACTIONS: ReadonlySet<IterationAction> = new Set(['delete'])

// Pipeline 状态展示文案与类型（独立于迭代状态列）
const PIPELINE_STATUS_TEXT: Record<string, string> = {
    in_pipeline: '运行中',
    in_review: '待评审',
    finalized: '已定稿',
}
const PIPELINE_STATUS_TYPE: Record<string, TagType> = {
    in_pipeline: 'success',
    in_review: 'warning',
    finalized: 'primary',
}

/**
 * 根据迭代状态返回可用操作列表（状态机）。
 * 独立导出以便单元测试直接验证状态机映射，无需挂载组件。
 */
export function getAvailableActions(status: string): IterationActionItem[] {
    const actions = STATUS_ACTION_MAP[status] ?? ['view_cases']
    return actions.map((cmd) => ({
        command: cmd,
        label: ACTION_LABELS[cmd],
        divided: DIVIDED_ACTIONS.has(cmd),
    }))
}

export function useIterationList() {
    const router = useRouter()
    const projectStore = useProjectStore()
    const iterationManager = useIterationManager()
    const loading = ref(false)

    const { pagination, resetToFirstPage, setTotal } = usePagination({
        defaultPageSize: 10,
    })

    const statusFilter = ref<string>('')

    const selectedProjectId = computed<number | null>({
        get: () => projectStore.currentProjectId,
        set: (val) => projectStore.setCurrentProject(val ?? null),
    })
    const currentProjectName = computed(() => projectStore.currentProjectName)
    const allIterations = computed<Iteration[]>(
        () => (iterationManager.iterations as Iteration[] | undefined) ?? []
    )

    // 后端列表接口不支持 status 参数，采用前端过滤
    const filteredIterations = computed<Iteration[]>(() => {
        if (!statusFilter.value) return allIterations.value
        return allIterations.value.filter((it) => it.status === statusFilter.value)
    })

    // 客户端分页切片
    const paginatedIterations = computed<Iteration[]>(() => {
        const start = (pagination.page - 1) * pagination.pageSize
        return filteredIterations.value.slice(start, start + pagination.pageSize)
    })

    function getStatusType(status: string): TagType {
        return iterationManager.getIterationStatusType(status)
    }
    function getStatusText(status: string): string {
        return iterationManager.getIterationStatusText(status)
    }
    function getStats(id: number): { files: number; prototypes: number } {
        return iterationManager.getIterationStatsById(id)
    }
    function getPipelineStatusText(status: string): string {
        return PIPELINE_STATUS_TEXT[status] ?? '未启动'
    }
    function getPipelineStatusType(status: string): TagType {
        return PIPELINE_STATUS_TYPE[status] ?? 'info'
    }

    async function loadData(): Promise<void> {
        if (!selectedProjectId.value) return
        loading.value = true
        try {
            await iterationManager.loadIterations(selectedProjectId.value)
            resetToFirstPage()
        } finally {
            loading.value = false
        }
    }

    /** 启动 Pipeline：调用 runPipeline，成功后跳转进度页 */
    async function handleRunPipeline(row: Iteration): Promise<void> {
        try {
            await ElMessageBox.confirm(
                `确认启动迭代 "${row.name}" 的 Pipeline？系统将自动采集信号、对齐历史用例并生成回归用例。`,
                '运行 Pipeline',
                { type: 'warning' }
            )
        } catch {
            return
        }
        // scenario=1 新需求场景
        const res = await runPipeline(row.id, 1)
        if (res.code === 0 && res.data) {
            const runId = res.data.run_id ?? res.data.pipeline_run_id
            ElMessage.success('Pipeline 已启动')
            if (runId) router.push(`/home/iteration/pipeline/${runId}`)
        } else {
            ElMessage.error(res.message || '启动 Pipeline 失败')
        }
    }

    /** 定稿：调用 finalizeIteration，成功后刷新列表 */
    async function handleFinalize(row: Iteration): Promise<void> {
        try {
            await ElMessageBox.confirm(
                `确认定稿迭代 "${row.name}"？定稿后将锁定迭代内容，不可再添加或修改资源。`,
                '定稿确认',
                { type: 'warning' }
            )
        } catch {
            return
        }
        const res = await finalizeIteration(row.id)
        if (res.code === 0) {
            ElMessage.success(`迭代 "${row.name}" 已定稿`)
            await loadData()
        } else {
            ElMessage.error(res.message || '定稿迭代失败')
        }
    }

    /** 归档：调用 archiveIteration，成功后刷新列表 */
    async function handleArchive(row: Iteration): Promise<void> {
        try {
            await ElMessageBox.confirm(
                `确认归档迭代 "${row.name}"？归档后迭代将变为只读。`,
                '归档确认',
                { type: 'warning' }
            )
        } catch {
            return
        }
        const res = await archiveIteration(row.id)
        if (res.code === 0) {
            ElMessage.success(`迭代 "${row.name}" 已归档`)
            await loadData()
        } else {
            ElMessage.error(res.message || '归档迭代失败')
        }
    }

    /** 删除：复用 iterationManager 的确认与调用 */
    async function handleDelete(row: Iteration): Promise<void> {
        const ok = await iterationManager.handleDeleteIteration(row)
        if (ok) await loadData()
    }

    /** 编辑：打开表单对话框 */
    function handleEdit(row: Iteration): void {
        iterationManager.handleEditIteration(row)
    }

    /** 查看 Pipeline 进度：跳转回归变更分析页（携带迭代上下文） */
    function handleViewPipeline(row: Iteration): void {
        router.push({
            name: 'IterationRegressionGenerate',
            query: { project_id: String(row.project_id), iteration_id: String(row.id) },
        })
    }

    /** 查看用例：跳转用例列表 */
    function handleViewCases(row: Iteration): void {
        router.push({ name: 'CaseList', query: { iteration_id: String(row.id) } })
    }

    /** 查看资源：跳转资源中心并携带迭代上下文，自动筛选该迭代的资源 */
    function handleViewResources(row: Iteration): void {
        router.push({
            name: 'RequirementResource',
            query: {
                project_id: String(row.project_id),
                iteration_id: String(row.id),
            },
        })
    }

    /** 查看评审：先获取最新评审 ID，再跳转评审 Inbox */
    async function handleViewReview(row: Iteration): Promise<void> {
        try {
            const res = await reviewApi.getReviewsByIteration(row.id)
            const reviews = res.data?.reviews ?? []
            if (reviews.length > 0) {
                router.push(`/home/iteration/review/${reviews[0].id}`)
            } else {
                await ElMessageBox.confirm(
                    '当前迭代暂无评审记录，是否前往评审 Inbox？',
                    '提示',
                    {
                        confirmButtonText: '前往评审 Inbox',
                        cancelButtonText: '取消',
                        type: 'info',
                    }
                )
                router.push('/home/iteration/review/0')
            }
        } catch (error: unknown) {
            if (error === 'cancel' || error === 'close') return
            ElMessage.error(error instanceof Error ? error.message : '跳转评审失败')
        }
    }

    /** 操作命令分发 */
    async function handleCommand(cmd: IterationAction, row: Iteration): Promise<void> {
        switch (cmd) {
            case 'run_pipeline':
                await handleRunPipeline(row)
                break
            case 'finalize':
                await handleFinalize(row)
                break
            case 'archive':
                await handleArchive(row)
                break
            case 'delete':
                await handleDelete(row)
                break
            case 'edit':
                handleEdit(row)
                break
            case 'view_pipeline':
                handleViewPipeline(row)
                break
            case 'view_review':
                await handleViewReview(row)
                break
            case 'view_cases':
                handleViewCases(row)
                break
            case 'view_resources':
                handleViewResources(row)
                break
        }
    }

    // 状态筛选变更：重置到第一页
    watch(statusFilter, () => resetToFirstPage())
    // 项目变更：重新加载
    watch(selectedProjectId, (val) => {
        if (val) void loadData()
        else iterationManager.iterations = []
    })
    // 同步过滤后总数到分页
    watch(filteredIterations, (list) => setTotal(list.length))

    onMounted(async () => {
        if (projectStore.projects.length === 0) {
            try {
                await projectStore.fetchProjects()
            } catch {
                // 忽略，用户可手动选择项目
            }
        }
        if (selectedProjectId.value) await loadData()
    })

    return {
        loading,
        selectedProjectId,
        currentProjectName,
        iterations: paginatedIterations,
        statusFilter,
        pagination,
        projectStore,
        iterationManager,
        statusOptions: ITERATION_STATUS_OPTIONS,
        getStatusType,
        getStatusText,
        getStats,
        getPipelineStatusType,
        getPipelineStatusText,
        getAvailableActions,
        loadData,
        handleCommand,
    }
}
