import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { pipelineApi } from '@/api/pipeline'
import ProjectAPI from '@/api/project'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

export function usePipelineDashboard() {
  const router = useRouter()
  const projectId = ref<number | undefined>(undefined)
  const days = ref(7)
  const projects = ref<Array<{ id: number; name: string }>>([])

  const overview = ref<Record<string, any>>({})
  const tokenUsage = ref<Array<any>>([])
  const runDuration = ref<Array<any>>([])
  const stepLatency = ref<Array<any>>([])
  const cacheHitRate = ref<Array<any>>([])
  const fmeaMetrics = ref<Array<any>>([])

  const tokenChartRef = ref<HTMLElement>()
  const durationChartRef = ref<HTMLElement>()
  const stepLatencyChartRef = ref<HTMLElement>()
  const cacheChartRef = ref<HTMLElement>()

  let tokenChart: EChartsType | null = null
  let durationChart: EChartsType | null = null
  let stepLatencyChart: EChartsType | null = null
  let cacheChart: EChartsType | null = null

  const overviewCards = computed(() => [
    {
      key: 'runs',
      title: '总运行',
      value: overview.value.total_runs ?? '-',
      suffix: '次',
      color: 'card-blue',
    },
    {
      key: 'success',
      title: '成功率',
      value: overview.value.success_rate ?? '-',
      suffix: '%',
      color: 'card-green',
    },
    {
      key: 'tokens',
      title: 'Token 消耗',
      value: overview.value.total_tokens ?? '-',
      suffix: '',
      color: 'card-purple',
    },
    {
      key: 'cost',
      title: '总成本',
      value: overview.value.total_cost_usd ?? '-',
      suffix: ' USD',
      color: 'card-orange',
    },
    {
      key: 'duration',
      title: '平均时长',
      value: overview.value.avg_duration_seconds ?? '-',
      suffix: ' 秒',
      color: 'card-cyan',
    },
    {
      key: 'cache',
      title: '缓存命中率',
      value: overview.value.cache_hit_rate ?? '-',
      suffix: '%',
      color: 'card-teal',
    },
  ])

  const goBack = () => {
    router.back()
  }

  async function fetchProjects() {
    try {
      const res = await ProjectAPI.getProjects({})
      projects.value = res?.data?.items ?? []
    } catch (e) {
      console.warn('获取项目列表失败:', e)
    }
  }

  function getDashboardParams() {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    return params
  }

  async function fetchOverview() {
    try {
      const res = await pipelineApi.getDashboardOverview(getDashboardParams())
      overview.value = res.data?.data ?? {}
    } catch (e) {
      console.warn('获取总览失败:', e)
    }
  }
  async function fetchTokenUsage() {
    try {
      const res = await pipelineApi.getDashboardTokenUsage(getDashboardParams())
      tokenUsage.value = (res.data?.data as any[]) || []
    } catch (e) {
      console.warn('获取Token消耗失败:', e)
    }
  }
  async function fetchRunDuration() {
    try {
      const res = await pipelineApi.getDashboardRunDuration(getDashboardParams())
      runDuration.value = (res.data?.data as any[]) || []
    } catch (e) {
      console.warn('获取运行时长失败:', e)
    }
  }
  async function fetchStepLatency() {
    try {
      const res = await pipelineApi.getDashboardStepLatency(getDashboardParams())
      stepLatency.value = (res.data?.data as any[]) || []
    } catch (e) {
      console.warn('获取Step耗时失败:', e)
    }
  }
  async function fetchCacheHitRate() {
    try {
      const res = await pipelineApi.getDashboardCacheHitRate(getDashboardParams())
      cacheHitRate.value = (res.data?.data as any[]) || []
    } catch (e) {
      console.warn('获取缓存命中率失败:', e)
    }
  }
  async function fetchFmeaMetrics() {
    try {
      const res = await pipelineApi.getMetricsSummary(getDashboardParams())
      fmeaMetrics.value = res.data?.data?.metrics ?? []
    } catch (e) {
      console.warn('获取FMEA指标失败:', e)
    }
  }

  function renderTokenChart() {
    if (!tokenChartRef.value) return
    if (!tokenChart) tokenChart = echarts.init(tokenChartRef.value)
    tokenChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['Prompt Tokens', 'Completion Tokens'] },
      xAxis: { type: 'category', data: tokenUsage.value.map((r: any) => r.date) },
      yAxis: { type: 'value' },
      series: [
        {
          name: 'Prompt Tokens',
          type: 'bar',
          stack: 'tokens',
          data: tokenUsage.value.map((r: any) => r.prompt_tokens),
          itemStyle: { color: '#409EFF' },
        },
        {
          name: 'Completion Tokens',
          type: 'bar',
          stack: 'tokens',
          data: tokenUsage.value.map((r: any) => r.completion_tokens),
          itemStyle: { color: '#67C23A' },
        },
      ],
    })
  }

  function renderDurationChart() {
    if (!durationChartRef.value) return
    if (!durationChart) durationChart = echarts.init(durationChartRef.value)
    durationChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: runDuration.value.map((r: any) => r.date) },
      yAxis: { type: 'value', name: '秒' },
      series: [
        {
          name: '平均时长',
          type: 'line',
          data: runDuration.value.map((r: any) => r.avg_duration_seconds),
          smooth: true,
          itemStyle: { color: '#E6A23C' },
        },
      ],
    })
  }

  function renderStepLatencyChart() {
    if (!stepLatencyChartRef.value) return
    if (!stepLatencyChart) stepLatencyChart = echarts.init(stepLatencyChartRef.value)
    stepLatencyChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: stepLatency.value.map((r: any) => r.step_name),
        axisLabel: { rotate: 30 },
      },
      yAxis: { type: 'value', name: '秒' },
      series: [
        {
          name: '平均耗时',
          type: 'bar',
          data: stepLatency.value.map((r: any) => r.avg_duration_seconds),
          itemStyle: { color: '#F56C6C' },
        },
      ],
    })
  }

  function renderCacheChart() {
    if (!cacheChartRef.value) return
    if (!cacheChart) cacheChart = echarts.init(cacheChartRef.value)
    cacheChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: cacheHitRate.value.map((r: any) => r.date) },
      yAxis: { type: 'value', name: '%', max: 100 },
      series: [
        {
          name: '命中率',
          type: 'line',
          data: cacheHitRate.value.map((r: any) => r.cache_hit_rate),
          smooth: true,
          areaStyle: { opacity: 0.3 },
          itemStyle: { color: '#909399' },
        },
      ],
    })
  }

  async function refreshAll() {
    await Promise.all([
      fetchOverview(),
      fetchTokenUsage(),
      fetchRunDuration(),
      fetchStepLatency(),
      fetchCacheHitRate(),
      fetchFmeaMetrics(),
    ])
    await nextTick()
    renderTokenChart()
    renderDurationChart()
    renderStepLatencyChart()
    renderCacheChart()
  }

  function handleResize() {
    tokenChart?.resize()
    durationChart?.resize()
    stepLatencyChart?.resize()
    cacheChart?.resize()
  }

  watch([projectId, days], () => {
    refreshAll()
  })

  onMounted(async () => {
    await fetchProjects()
    await refreshAll()
    window.addEventListener('resize', handleResize)
  })
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    tokenChart?.dispose()
    durationChart?.dispose()
    stepLatencyChart?.dispose()
    cacheChart?.dispose()
  })

  return {
    projectId,
    days,
    projects,
    overviewCards,
    fmeaMetrics,
    tokenChartRef,
    durationChartRef,
    stepLatencyChartRef,
    cacheChartRef,
    goBack,
    refreshAll,
  }
}
