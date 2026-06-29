/**
 * 快速测试共享类型、stage 映射表与数据映射器。
 *
 * spec 偏离说明（stage→中文标签映射）：
 * spec UX 章节描述 4 阶段为「站点探索 / 用例生成 / 任务执行 / 报告生成」，
 * 但后端实际推送 `site_exploring / case_generating / task_assembling / completed`，
 * 其中 task_assembling 已合并 spec 的「任务执行 + 报告生成」两阶段。
 * 前端通过 STAGE_LABELS 将后端 4 阶段映射到 spec UX 4 阶段展示文案。
 */
import type { QuickTestStage } from '@/api/quickTest'
import type { Report, TestCaseResult, DefectItem } from '@/api/report'

/** 用例状态枚举：与 CaseCard 渲染逻辑对齐 */
export type CaseStatus = 'pending' | 'running' | 'passed' | 'failed'

/** 缺陷严重度：1=P0致命 2=P1严重 3=P2一般 4=P3轻微（与后端 DefectItem.severity 对齐） */
export type DefectSeverity = 1 | 2 | 3 | 4

/** 单步执行结果：元素验证状态由执行引擎回填 */
export interface CaseStep {
    step: number
    description: string
    action: string
    target_element: string
    expected_result: string
    actual_result?: string
    element_verified?: boolean
    screenshot?: string
}

/** 用例卡片数据模型：进度视图与结果视图复用 */
export interface CaseData {
    id: number
    title: string
    status: CaseStatus
    steps: CaseStep[]
    expected_result?: string
    actual_result?: string
    failure_reason?: string
    duration_sec?: number
}

/** 缺陷数据模型：用于结果视图缺陷清单展示 */
export interface DefectData {
    bug_no: string
    title: string
    severity: DefectSeverity
    module: string
    ux_category: string
    status: string
    reproduction_steps: string | null
    evidence: Record<string, unknown> | null
    fix_suggestion: string | null
    case_id?: number
    screenshot?: string
}

/** 报告摘要统计：环形图与统计卡使用 */
export interface SummaryStats {
    total: number
    passed: number
    failed: number
    pass_rate: number
    duration_sec: number
    severity_dist: { p0: number; p1: number; p2: number; p3: number }
}

/**
 * WS 推送 detail 在 completed 阶段可能携带的结果负载。
 * 字段全部可选：后端可能仅推送进度而将明细留在报告接口。
 */
export interface QuickTestResultDetail {
    cases?: CaseData[]
    defects?: DefectData[]
    summary?: Partial<SummaryStats>
    explored_pages?: Array<{ url: string; title?: string; screenshot?: string }>
}

/**
 * stage → 中文标签映射表（spec 偏离合并点）。
 * task_assembling 映射为「任务执行」（合并 spec 任务执行+报告生成），
 * completed 映射为「报告生成」。
 */
export const STAGE_LABELS: Record<QuickTestStage, string> = {
    pending: '等待开始',
    site_exploring: '站点探索',
    case_generating: '用例生成',
    task_assembling: '任务执行',
    executing: '任务执行',
    completed: '报告生成',
    failed: '执行失败',
    stopped: '已停止',
}

/**
 * stage → 进度条百分比区间映射（用于进度视图阶段进度估算）。
 * 值为 [下限, 上限] 闭区间，completed 固定 100。
 */
export const STAGE_PROGRESS_RANGE: Record<QuickTestStage, [number, number]> = {
    pending: [0, 5],
    site_exploring: [10, 30],
    case_generating: [40, 60],
    task_assembling: [70, 90],
    executing: [70, 90],
    completed: [100, 100],
    failed: [0, 0],
    stopped: [0, 0],
}

/** 进度视图 4 阶段展示定义（spec UX 对齐） */
export interface ProgressStageDef {
    key: string
    label: string
    stages: QuickTestStage[]
}

export const PROGRESS_STAGES: ProgressStageDef[] = [
    { key: 'explore', label: '站点探索', stages: ['site_exploring'] },
    { key: 'generate', label: '用例生成', stages: ['case_generating'] },
    { key: 'execute', label: '任务执行', stages: ['task_assembling', 'executing'] },
    { key: 'report', label: '报告生成', stages: ['completed'] },
]

/**
 * 计算当前进度阶段索引（0-3），未知 stage 兜底 0。
 * @param stage 后端推送的 current_stage
 */
export function getProgressStageIndex(stage: QuickTestStage): number {
    const idx = PROGRESS_STAGES.findIndex((s) => s.stages.includes(stage))
    return idx < 0 ? 0 : idx
}

/**
 * 将后端 TestCaseResult 映射为 CaseCard 数据模型。
 * 报告用例不含步骤明细，steps 置空数组，状态由 status 字符串窄化。
 */
export function testCaseResultToCaseData(r: TestCaseResult): CaseData {
    const status = narrowCaseStatus(r.status)
    return {
        id: r.test_case_id,
        title: r.test_case_name || `用例 #${r.test_case_id}`,
        status,
        steps: [],
        expected_result: r.expected_result,
        actual_result: r.actual_result,
        duration_sec: computeDurationSec(r.start_time, r.end_time),
        failure_reason: status === 'failed' ? r.actual_result : undefined,
    }
}

/** 后端 status 字符串窄化为 CaseStatus 枚举，未知值兜底 pending */
export function narrowCaseStatus(raw: string): CaseStatus {
    const s = (raw || '').toLowerCase()
    if (s.includes('pass') || s === 'success' || s === '成功') return 'passed'
    if (s.includes('fail') || s === 'error' || s === '失败') return 'failed'
    if (s.includes('run') || s === 'running' || s === '执行中') return 'running'
    return 'pending'
}

/** 将后端 DefectItem 映射为缺陷展示模型，severity 越界兜底 P3 */
export function defectItemToDefectData(d: DefectItem): DefectData {
    const sev = ((n: number): DefectSeverity => {
        if (n === 1 || n === 2 || n === 3) return n
        return 4
    })(d.severity)
    return {
        bug_no: d.bug_no,
        title: d.title,
        severity: sev,
        module: d.module,
        ux_category: d.ux_category,
        status: d.status,
        reproduction_steps: d.reproduction_steps,
        evidence: d.evidence,
        fix_suggestion: d.fix_suggestion,
    }
}

/** ISO8601 时间区间计算耗时秒，缺值返回 0 */
function computeDurationSec(start?: string, end?: string): number {
    if (!start || !end) return 0
    const t0 = Date.parse(start)
    const t1 = Date.parse(end)
    if (Number.isNaN(t0) || Number.isNaN(t1) || t1 < t0) return 0
    return Math.round((t1 - t0) / 1000)
}

/** 从 Report 聚合摘要统计：总数/通过/失败/通过率/耗时/严重度分布 */
export function buildSummaryFromReport(report: Report): SummaryStats {
    const cases = report.test_cases || []
    const total = cases.length
    const passed = cases.filter((c) => narrowCaseStatus(c.status) === 'passed').length
    const failed = cases.filter((c) => narrowCaseStatus(c.status) === 'failed').length
    const pass_rate = total > 0 ? Math.round((passed / total) * 100) : 0
    const duration_sec = report.execution_time || 0
    const defects = report.content?.defect_list || []
    const severity_dist = { p0: 0, p1: 0, p2: 0, p3: 0 }
    for (const d of defects) {
        if (d.severity === 1) severity_dist.p0 += 1
        else if (d.severity === 2) severity_dist.p1 += 1
        else if (d.severity === 3) severity_dist.p2 += 1
        else severity_dist.p3 += 1
    }
    return { total, passed, failed, pass_rate, duration_sec, severity_dist }
}

/** 严重度 → 中文标签 */
export const SEVERITY_LABELS: Record<DefectSeverity, string> = {
    1: 'P0 致命',
    2: 'P1 严重',
    3: 'P2 一般',
    4: 'P3 轻微',
}

/** 严重度 → el-tag 类型配色（P0 红色醒目） */
export const SEVERITY_TAG_TYPE: Record<DefectSeverity, 'danger' | 'warning' | 'info' | 'primary'> = {
    1: 'danger',
    2: 'warning',
    3: 'info',
    4: 'primary',
}
