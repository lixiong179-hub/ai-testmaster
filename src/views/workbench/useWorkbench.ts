/**
 * 工作台首页组合式函数
 *
 * 聚合四个区块数据：当前项目概览、待我评审、最近任务、AI 成本趋势。
 * 各区块独立加载（互不阻塞），无项目时由视图层渲染创建引导。
 *
 * 说明：后端暂无工作台聚合 API，此处组合现有 review/iteration/test-task/ai-invocation 接口；
 * 质量分等未落地的指标以 TODO 标注，待后端聚合接口上线后替换。
 */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/store/project'
import ProjectAPI from '@/api/project'
import { iterationApi } from '@/api/iteration'
import { reviewApi } from '@/api/review'
import testTaskApi from '@/api/testTask'
import { aiInvocationApi, usdToCny } from '@/api/aiInvocation'
import { echarts, type EChartsType } from '@/utils/echarts'
import {
    type ProjectOverview,
    type PendingReviewItem,
    type RecentTaskItem,
    type AICostTrendPoint,
    TREND_DAYS,
    REVIEW_ITERATION_SCAN_LIMIT,
    buildDateRange,
    extractTaskItems,
    extractTotal,
    computePassRate,
} from './workbenchHelpers'

export type {
    ProjectOverview,
    PendingReviewItem,
    RecentTaskItem,
    AICostTrendPoint,
}

export function useWorkbench() {
    const router = useRouter()
    const projectStore = useProjectStore()

    const currentProjectId = computed(() => projectStore.currentProjectId)
    const hasProject = computed(
        () => currentProjectId.value !== null && currentProjectId.value > 0
    )

    // 各区块独立加载状态，互不阻塞
    const overviewLoading = ref(false)
    const reviewsLoading = ref(false)
    const tasksLoading = ref(false)
    const costLoading = ref(false)

    const overview = ref<ProjectOverview | null>(null)
    const pendingReviews = ref<PendingReviewItem[]>([])
    const recentTasks = ref<RecentTaskItem[]>([])
    const aiCostTrend = ref<AICostTrendPoint[]>([])

    // AI 成本图表
    const costChartRef = ref<HTMLElement>()
    let costChart: EChartsType | null = null

    const totalCostCny = computed(() =>
        aiCostTrend.value.reduce((sum, p) => sum + p.costCny, 0).toFixed(2)
    )
    const totalCalls = computed(() =>
        aiCostTrend.value.reduce((sum, p) => sum + p.calls, 0)
    )

    /** 模板 ref 回调：仅接受 HTMLElement，避免组件卸载时传入 null 报错 */
    function setCostChartRef(el: unknown): void {
        costChartRef.value = el instanceof HTMLElement ? el : undefined
    }

    // ============== 数据加载 ==============

    /** 当前项目概览：组合项目详情 + 迭代数 + 用例数 + 任务通过率 */
    // TODO: 后端暂无聚合接口，需求规模以迭代总数近似；待 GET /project/{id}/overview 落地后替换
    async function fetchProjectOverview(pid: number): Promise<void> {
        overviewLoading.value = true
        try {
            const [detailRes, iterRes, casesRes, tasksRes] = await Promise.all([
                ProjectAPI.getProjectDetail(pid),
                iterationApi.getIterations(pid, 1, 1).catch(() => null),
                testTaskApi.getProjectCases(pid, { page: 1, page_size: 1 }).catch(() => null),
                testTaskApi
                    .getTaskList({ project_id: pid, page: 1, page_size: 100 })
                    .catch(() => null),
            ])
            overview.value = {
                projectId: pid,
                name: detailRes?.data?.name ?? '',
                requirementCount: iterRes?.data?.total ?? 0,
                caseCount: extractTotal(casesRes),
                // TODO: 后端暂无项目质量分接口，待 GET /project/{id}/quality-score 落地后接入
                qualityScore: null,
                passRate: computePassRate(tasksRes),
            }
        } catch (err) {
            console.warn('工作台-项目概览加载失败:', err)
        } finally {
            overviewLoading.value = false
        }
    }

    /** 待我评审：扫描最近迭代下的评审记录，取 status=in_progress 的前 5 条 */
    // TODO: 后端暂无"待我评审"专用端点，此处按迭代扫描聚合；待 GET /review/pending?user=me 落地后替换
    async function fetchPendingReviews(pid: number): Promise<void> {
        reviewsLoading.value = true
        try {
            const iterRes = await iterationApi.getIterations(pid, 1, 50)
            const iterations = iterRes?.data?.items ?? []
            const candidates = iterations.slice(0, REVIEW_ITERATION_SCAN_LIMIT)
            const reviewsNested = await Promise.all(
                candidates.map((it) =>
                    reviewApi.getReviewsByIteration(it.id).catch(() => null)
                )
            )
            const flat: PendingReviewItem[] = []
            for (const res of reviewsNested) {
                const reviews = res?.data?.reviews ?? []
                for (const rv of reviews) {
                    if (rv.status === 'in_progress') {
                        flat.push({
                            reviewId: rv.id,
                            iterationId: rv.iteration_id,
                            kind: rv.kind,
                            status: rv.status,
                            createdAt: rv.created_at,
                        })
                    }
                }
            }
            pendingReviews.value = flat.slice(0, 5)
        } catch (err) {
            console.warn('工作台-待我评审加载失败:', err)
            pendingReviews.value = []
        } finally {
            reviewsLoading.value = false
        }
    }

    /** 最近任务：取该项目最近 5 个任务 */
    async function fetchRecentTasks(pid: number): Promise<void> {
        tasksLoading.value = true
        try {
            const res = await testTaskApi.getTaskList({
                project_id: pid,
                page: 1,
                page_size: 5,
            })
            recentTasks.value = extractTaskItems(res).map((t) => ({
                id: t.id,
                taskName: t.task_name,
                status: t.status,
                successCount: t.success_count,
                failCount: t.fail_count,
                totalCount: t.total_count,
                createTime: t.create_time,
            }))
        } catch (err) {
            console.warn('工作台-最近任务加载失败:', err)
            recentTasks.value = []
        } finally {
            tasksLoading.value = false
        }
    }

    /** AI 成本趋势：近 7 天按日期聚合 */
    async function fetchAICostTrend(pid: number): Promise<void> {
        costLoading.value = true
        try {
            const range = buildDateRange(TREND_DAYS)
            const res = await aiInvocationApi.getStats({
                project_id: pid,
                ...range,
                group_by: 'date',
            })
            const items = res?.data?.items ?? []
            const sorted = [...items].sort((a, b) =>
                a.group_key.localeCompare(b.group_key)
            )
            aiCostTrend.value = sorted.map((it) => ({
                date: it.group_key,
                costCny: usdToCny(it.total_cost_usd),
                calls: it.total_calls,
            }))
            await nextTick()
            renderCostChart()
        } catch (err) {
            console.warn('工作台-AI成本趋势加载失败:', err)
            aiCostTrend.value = []
        } finally {
            costLoading.value = false
        }
    }

    /** 渲染成本趋势折线图 */
    function renderCostChart(): void {
        if (!costChartRef.value) return
        if (!costChart) costChart = echarts.init(costChartRef.value)
        const data = aiCostTrend.value
        costChart.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 48, right: 16, bottom: 28, top: 16 },
            xAxis: {
                type: 'category',
                data: data.map((d) => d.date),
                axisLabel: { rotate: 30 },
            },
            yAxis: { type: 'value', name: '元' },
            series: [
                {
                    name: '成本(元)',
                    type: 'line',
                    smooth: true,
                    areaStyle: { opacity: 0.2 },
                    itemStyle: { color: '#E6A23C' },
                    data: data.map((d) => d.costCny),
                },
            ],
        })
    }

    /** 并行加载所有区块（各区块独立，互不阻塞） */
    function fetchAll(): void {
        const pid = currentProjectId.value
        if (!pid || pid <= 0) return
        void fetchProjectOverview(pid)
        void fetchPendingReviews(pid)
        void fetchRecentTasks(pid)
        void fetchAICostTrend(pid)
    }

    function handleResize(): void {
        costChart?.resize()
    }

    // ============== 导航 ==============
    function goToCreateProject(): void {
        router.push({ name: 'ProjectList' })
    }

    function goToProjectList(): void {
        router.push({ name: 'ProjectList' })
    }

    function goToTaskList(): void {
        const pid = currentProjectId.value
        if (pid) router.push(`/home/task/list/${pid}`)
        else router.push({ name: 'TaskOverview' })
    }

    function goToTaskDetail(taskId: number): void {
        const pid = currentProjectId.value ?? 0
        router.push(`/home/task/detail/${taskId}?project_id=${pid}`)
    }

    function goToReviewInbox(reviewId: number): void {
        router.push({ name: 'IterationReviewInbox', params: { reviewId } })
    }

    function goToAICostDashboard(): void {
        router.push({ name: 'AICostDashboard' })
    }

    // ============== 生命周期 ==============
    onMounted(async () => {
        window.addEventListener('resize', handleResize)
        // 确保项目列表已加载，用于判断是否存在项目
        if (projectStore.projects.length === 0) {
            try {
                await projectStore.fetchProjects()
            } catch {
                /* 项目列表加载失败不阻塞工作台渲染 */
            }
        }
        // 全局上下文无当前项目但存在项目时，自动继承首个项目，避免工作台空白
        if (!hasProject.value && projectStore.projects.length > 0) {
            projectStore.setCurrentProject(projectStore.projects[0].id)
            // currentProjectId 变化由下方 watch 接管触发 fetchAll
            return
        }
        fetchAll()
    })

    // 项目上下文切换时重新加载所有区块
    watch(currentProjectId, (newPid, oldPid) => {
        if (!newPid || newPid === oldPid) return
        fetchAll()
    })

    onUnmounted(() => {
        window.removeEventListener('resize', handleResize)
        costChart?.dispose()
        costChart = null
    })

    return {
        hasProject,
        overview,
        overviewLoading,
        pendingReviews,
        reviewsLoading,
        recentTasks,
        tasksLoading,
        aiCostTrend,
        costLoading,
        totalCostCny,
        totalCalls,
        setCostChartRef,
        goToCreateProject,
        goToProjectList,
        goToTaskList,
        goToTaskDetail,
        goToReviewInbox,
        goToAICostDashboard,
    }
}
