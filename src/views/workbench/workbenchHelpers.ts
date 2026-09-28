/**
 * 工作台首页：纯类型定义与无副作用工具函数
 *
 * 从 useWorkbench.ts 拆分，保持单文件 ≤350 行；此处仅包含可独立测试的纯逻辑。
 */
// ============== 工作台数据类型 ==============
export interface ProjectOverview {
    projectId: number
    name: string
    requirementCount: number
    caseCount: number
    /** 项目质量分；后端暂无接口，null 表示未采集 */
    qualityScore: number | null
    /** 执行通过率（0-100） */
    passRate: number
}

export interface PendingReviewItem {
    reviewId: number
    iterationId: number
    kind: string
    status: string
    createdAt: string | null
}

export interface RecentTaskItem {
    id: number
    taskName: string
    status: number
    successCount: number
    failCount: number
    totalCount: number
    createTime: string
}

export interface AICostTrendPoint {
    date: string
    costCny: number
    calls: number
}

// ============== 常量 ==============
export const TREND_DAYS = 7
/** 评审聚合时扫描的迭代上限，控制并发请求数避免 N+1 */
export const REVIEW_ITERATION_SCAN_LIMIT = 10

// ============== 内部类型 ==============
interface TaskListItem {
    id: number
    task_name: string
    status: number
    success_count: number
    fail_count: number
    total_count: number
    create_time: string
}

// ============== 工具函数 ==============
/** 构造最近 N 天的日期区间（YYYY-MM-DD） */
export function buildDateRange(days: number): { start_date: string; end_date: string } {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - days + 1)
    return {
        start_date: start.toISOString().split('T')[0],
        end_date: end.toISOString().split('T')[0],
    }
}

/** 从列表响应中提取 items，兼容 data.items 与平铺 items 两种形态 */
export function extractTaskItems(response: unknown): TaskListItem[] {
    const r = response as {
        data?: { items?: TaskListItem[] }
        items?: TaskListItem[]
    } | undefined
    return r?.data?.items ?? r?.items ?? []
}

/** 从列表响应中提取 total */
export function extractTotal(response: unknown): number {
    const r = response as {
        data?: { total?: number }
        total?: number
    } | undefined
    return r?.data?.total ?? r?.total ?? 0
}

/** 由任务列表聚合执行通过率：sum(success_count) / sum(total_count) */
export function computePassRate(response: unknown): number {
    const items = extractTaskItems(response)
    let success = 0
    let total = 0
    for (const t of items) {
        success += t.success_count ?? 0
        total += t.total_count ?? 0
    }
    return total > 0 ? Math.round((success / total) * 100) : 0
}
