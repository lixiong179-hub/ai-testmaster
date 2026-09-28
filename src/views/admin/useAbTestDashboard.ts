/**
 * A/B 实验看板组合式函数
 *
 * 管理实验列表、当前选中实验与其汇总数据，派生 control/treatment
 * 各指标对比行（均值、差异百分比、改善判定）。所有 IO 异常均捕获并提示。
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  abTestApi,
  AB_TEST_METRIC_LABELS,
  AB_TEST_METRIC_DIRECTION,
} from '@/api/abTest'
import type {
  AbTestExperiment,
  AbTestSummary,
  AbTestMetricName,
  AbTestVariantStats,
} from '@/api/abTest'

/** 指标对比行：control/treatment 横向对比结果 */
export interface MetricComparisonRow {
  metricName: AbTestMetricName
  label: string
  direction: 'higher' | 'lower'
  controlMean: number | null
  treatmentMean: number | null
  controlSample: number
  treatmentSample: number
  /** 差异百分比：(treatment - control) / |control| * 100 */
  diffPercent: number | null
  /** treatment 相对 control 是否更优（结合方向判定） */
  improved: boolean | null
}

/** 计算差异百分比；control 为 0 时无法计算返回 null */
function calcDiffPercent(control: number, treatment: number): number | null {
  if (control === 0) return null
  return Number((((treatment - control) / Math.abs(control)) * 100).toFixed(2))
}

/** 从变体统计中安全读取某指标的均值与样本数 */
function pickMean(
  stats: AbTestVariantStats | undefined,
  name: AbTestMetricName
): { mean: number | null; sample: number } {
  if (!stats || !stats[name]) return { mean: null, sample: 0 }
  const stat = stats[name] as { mean: number; sample_count: number }
  return { mean: stat.mean, sample: stat.sample_count }
}

/** 全部合法指标名（按映射顺序遍历，生成完整对比行） */
const ALL_METRIC_NAMES = Object.keys(AB_TEST_METRIC_LABELS) as AbTestMetricName[]

export function useAbTestDashboard() {
  const router = useRouter()
  const loading = ref(false)
  const experiments = ref<AbTestExperiment[]>([])
  const experimentId = ref<string>('')
  const summary = ref<AbTestSummary | null>(null)
  const errorMessage = ref('')

  /** 指标对比行（遍历全部 9 项指标，未覆盖的指标均值为 null） */
  const comparisonRows = computed<MetricComparisonRow[]>(() => {
    const variants = summary.value?.variants ?? {}
    const controlStats = variants['control']
    const treatmentStats = variants['treatment']
    return ALL_METRIC_NAMES.map((name): MetricComparisonRow => {
      const c = pickMean(controlStats, name)
      const t = pickMean(treatmentStats, name)
      const diff =
        c.mean !== null && t.mean !== null ? calcDiffPercent(c.mean, t.mean) : null
      let improved: boolean | null = null
      if (diff !== null) {
        const direction = AB_TEST_METRIC_DIRECTION[name]
        // direction=higher: treatment 高于 control 为优；lower 反之
        improved = direction === 'higher' ? diff > 0 : diff < 0
      }
      return {
        metricName: name,
        label: AB_TEST_METRIC_LABELS[name],
        direction: AB_TEST_METRIC_DIRECTION[name],
        controlMean: c.mean,
        treatmentMean: t.mean,
        controlSample: c.sample,
        treatmentSample: t.sample,
        diffPercent: diff,
        improved,
      }
    })
  })

  /** 是否存在可展示的汇总数据 */
  const hasData = computed(
    () =>
      summary.value !== null &&
      Object.keys(summary.value.variants ?? {}).length > 0
  )

  const goBack = (): void => {
    router.back()
  }

  /** 获取实验列表，默认选中首个实验 */
  async function fetchExperiments(): Promise<void> {
    loading.value = true
    errorMessage.value = ''
    try {
      const res = await abTestApi.listExperiments({ page: 1, page_size: 100 })
      experiments.value = res.data?.items ?? []
      if (experiments.value.length > 0 && !experimentId.value) {
        experimentId.value = experiments.value[0].experiment_id
      }
    } catch (e) {
      errorMessage.value = e instanceof Error ? e.message : '获取实验列表失败'
      ElMessage.warning(errorMessage.value)
    } finally {
      loading.value = false
    }
  }

  /** 获取当前实验的汇总数据 */
  async function fetchSummary(): Promise<void> {
    if (!experimentId.value) {
      summary.value = null
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const res = await abTestApi.getExperimentSummary(experimentId.value)
      summary.value = res.data ?? null
    } catch (e) {
      errorMessage.value = e instanceof Error ? e.message : '获取实验汇总失败'
      ElMessage.warning(errorMessage.value)
      summary.value = null
    } finally {
      loading.value = false
    }
  }

  /** 刷新全部：先拉取实验列表，再拉取当前实验汇总 */
  async function refreshAll(): Promise<void> {
    await fetchExperiments()
    await fetchSummary()
  }

  /** 切换实验时重新加载汇总 */
  watch(experimentId, () => {
    fetchSummary()
  })

  onMounted(() => {
    refreshAll()
  })

  return {
    loading,
    experiments,
    experimentId,
    summary,
    comparisonRows,
    hasData,
    errorMessage,
    goBack,
    refreshAll,
  }
}

export default useAbTestDashboard
