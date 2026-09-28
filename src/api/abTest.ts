/**
 * A/B 测试指标 API 模块
 *
 * 对接后端 /api/v1/ab-test 端点，提供实验列表、实验汇总与指标记录能力。
 * 汇总数据按变体（control/treatment）分组，包含均值、标准差和样本数，
 * 用于对比实验效果。指标名称与后端 VALID_METRIC_NAMES 白名单严格对齐。
 */
import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'

// ============== 类型定义 ==============

/** 变体标识：control 为对照组，treatment 为实验组 */
export type AbTestVariant = 'control' | 'treatment'

/**
 * 合法指标名称（与后端 ab_test_service.VALID_METRIC_NAMES 白名单对齐）
 * 共 9 项：步骤可执行率、需求对齐率、无关元素引入率、上下文Token数、
 * 人工二次修改率、Evidence引用准确率、历史过滤准确率、完整性评分有效性、完整性评分
 */
export type AbTestMetricName =
  | 'step_executable_rate'
  | 'requirement_alignment_rate'
  | 'irrelevant_element_rate'
  | 'context_token_count'
  | 'manual_revision_rate'
  | 'evidence_refs_accuracy'
  | 'history_filter_accuracy'
  | 'completeness_score_effectiveness'
  | 'completeness_score'

/** 指标中文名称映射，用于看板展示 */
export const AB_TEST_METRIC_LABELS: Record<AbTestMetricName, string> = {
  step_executable_rate: '步骤可执行率',
  requirement_alignment_rate: '需求对齐率',
  irrelevant_element_rate: '无关元素引入率',
  context_token_count: '上下文Token数',
  manual_revision_rate: '人工二次修改率',
  evidence_refs_accuracy: 'Evidence引用准确率',
  history_filter_accuracy: '历史过滤准确率',
  completeness_score_effectiveness: '完整性评分有效性',
  completeness_score: '完整性评分',
}

/**
 * 指标优化方向：higher=越高越好，lower=越低越好
 * 用于判定 treatment 相对 control 是否为改善
 */
export const AB_TEST_METRIC_DIRECTION: Record<AbTestMetricName, 'higher' | 'lower'> = {
  step_executable_rate: 'higher',
  requirement_alignment_rate: 'higher',
  irrelevant_element_rate: 'lower',
  context_token_count: 'lower',
  manual_revision_rate: 'lower',
  evidence_refs_accuracy: 'higher',
  history_filter_accuracy: 'higher',
  completeness_score_effectiveness: 'higher',
  completeness_score: 'higher',
}

/** 实验列表项：实验ID及其样本数 */
export interface AbTestExperiment {
  experiment_id: string
  sample_count: number
}

/** 实验列表分页响应 */
export interface AbTestExperimentListResponse {
  items: AbTestExperiment[]
  total: number
  page: number
  page_size: number
}

/** 实验列表查询参数 */
export interface AbTestExperimentListParams {
  page?: number
  page_size?: number
}

/** 单个指标在某变体下的统计信息 */
export interface AbTestMetricStat {
  /** 均值 */
  mean: number
  /** 标准差 */
  std_dev: number
  /** 样本数 */
  sample_count: number
}

/** 变体下各指标的统计映射（metric_name -> stat），Partial 因实验可能未覆盖全部指标 */
export type AbTestVariantStats = Partial<Record<AbTestMetricName, AbTestMetricStat>>

/**
 * 实验汇总：variants 的 key 为变体标识（control/treatment），
 * value 为该变体下各指标的统计信息
 */
export interface AbTestSummary {
  experiment_id: string
  variants: Record<string, AbTestVariantStats>
}

/** 指标记录请求体（与后端 MetricCreateRequest 对齐） */
export interface AbTestMetricCreatePayload {
  variant: AbTestVariant
  metric_name: AbTestMetricName
  metric_value: number
  project_id?: number
  test_point_id?: number
  detail?: Record<string, unknown>
}

/** 指标记录响应 */
export interface AbTestMetricRecord {
  id: number
  experiment_id: string
  variant: AbTestVariant
  metric_name: AbTestMetricName
  metric_value: number
  created_at: string
}

// ============== API 封装 ==============

export const abTestApi = {
  /**
   * 获取实验列表（分页）
   *
   * 后端按 experiment_id 分组返回各实验的样本数，
   * 看板用于下拉选择当前查看的实验。
   */
  listExperiments: async (
    params: AbTestExperimentListParams = {}
  ): Promise<ApiResponse<AbTestExperimentListResponse>> => {
    return request.get('/api/v1/ab-test/experiments', {
      params: { page: 1, page_size: 20, ...params },
    }) as unknown as Promise<ApiResponse<AbTestExperimentListResponse>>
  },

  /**
   * 获取实验汇总（control/treatment 各指标均值/标准差/样本数）
   *
   * 后端按变体分组聚合，前端据此计算差异百分比与改善判定。
   */
  getExperimentSummary: async (
    experimentId: string
  ): Promise<ApiResponse<AbTestSummary>> => {
    return request.get(
      `/api/v1/ab-test/experiments/${encodeURIComponent(experimentId)}/summary`
    ) as unknown as Promise<ApiResponse<AbTestSummary>>
  },

  /**
   * 记录一条指标
   *
   * 写入时后端校验 metric_name 白名单与项目归属权，
   * project_id 非空时必须属于当前登录用户。
   */
  recordMetric: async (
    experimentId: string,
    payload: AbTestMetricCreatePayload
  ): Promise<ApiResponse<AbTestMetricRecord>> => {
    return request.post(
      `/api/v1/ab-test/experiments/${encodeURIComponent(experimentId)}/metrics`,
      payload
    ) as unknown as Promise<ApiResponse<AbTestMetricRecord>>
  },
}

export default abTestApi
