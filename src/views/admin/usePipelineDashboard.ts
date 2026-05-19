import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import * as echarts from 'echarts'

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

  let tokenChart: echarts.ECharts | null = null
  let durationChart: echarts.ECharts | null = null
  let stepLatencyChart: echarts.ECharts | null = null
  let cacheChart: echarts.ECharts | null = null

  const overviewCards = computed(() => [
    { key: 'runs', title: '总运行', value: overview.value.total_runs ?? '-', suffix: '次', color: 'card-blue' },
    { key: 'success', title: '成功率', value: overview.value.success_rate ?? '-', suffix: '%', color: 'card-green' },
    { key: 'tokens', title: 'Token 消耗', value: overview.value.total_tokens ?? '-', suffix: '', color: 'card-purple' },
    { key: 'cost', title: '总成本', value: overview.value.total_cost_usd ?? '-', suffix: ' USD', color: 'card-orange' },
    { key: 'duration', title: '平均时长', value: overview.value.avg_duration_seconds ?? '-', suffix: ' 秒', color: 'card-cyan' },
    { key: 'cache', title: '缓存命中率', value: overview.value.cache_hit_rate ?? '-', suffix: '%', color: 'card-teal' },
  ])

  const goBack = () => { router.back() }

  async function fetchProjects() {
    try {
      const res = await request.get('/api/v1/project/list')
      projects.value = res.data?.data?.items ?? res.data?.items ?? []
    } catch (e) { console.warn('获取项目列表失败:', e) }
  }

  async function fetchWithParams(url: string) {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get(url, { params })
    return res.data?.data ?? {}
  }

  async function fetchOverview() { try { overview.value = await fetchWithParams('/api/v1/pipeline/dashboard/overview') } catch (e) { console.warn('获取总览失败:', e) } }
  async function fetchTokenUsage() { try { tokenUsage.value = (await fetchWithParams('/api/v1/pipeline/dashboard/token-usage')) as any[] || [] } catch (e) { console.warn('获取Token消耗失败:', e) } }
  async function fetchRunDuration() { try { runDuration.value = (await fetchWithParams('/api/v1/pipeline/dashboard/run-duration')) as any[] || [] } catch (e) { console.warn('获取运行时长失败:', e) } }
  async function fetchStepLatency() { try { stepLatency.value = (await fetchWithParams('/api/v1/pipeline/dashboard/step-latency')) as any[] || [] } catch (e) { console.warn('获取Step耗时失败:', e) } }
  async function fetchCacheHitRate() { try { cacheHitRate.value = (await fetchWithParams('/api/v1/pipeline/dashboard/cache-hit-rate')) as any[] || [] } catch (e) { console.warn('获取缓存命中率失败:', e) } }
  async function fetchFmeaMetrics() {
    try {
      const params: Record<string, any> = { days: days.value }
      if (projectId.value) params.project_id = projectId.value
      const res = await request.get('/api/v1/pipeline/metrics/summary', { params })
      fmeaMetrics.value = res.data?.data?.metrics ?? []
    } catch (e) { console.warn('获取FMEA指标失败:', e) }
  }

  function renderTokenChart() {
    if (!tokenChartRef.value) return
    if (!tokenChart) tokenChart = echarts.init(tokenChartRef.value)
    tokenChart.setOption({
      tooltip: { trigger: 'axis' }, legend: { data: ['Prompt Tokens', 'Completion Tokens'] },
      xAxis: { type: 'category', data: tokenUsage.value.map((r: any) => r.date) }, yAxis: { type: 'value' },
      series: [
        { name: 'Prompt Tokens', type: 'bar', stack: 'tokens', data: tokenUsage.value.map((r: any) => r.prompt_tokens), itemStyle: { color: '#409EFF' } },
        { name: 'Completion Tokens', type: 'bar', stack: 'tokens', data: tokenUsage.value.map((r: any) => r.completion_tokens), itemStyle: { color: '#67C23A' } },
      ],
    })
  }

  function renderDurationChart() {
    if (!durationChartRef.value) return
    if (!durationChart) durationChart = echarts.init(durationChartRef.value)
    durationChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: runDuration.value.map((r: any) => r.date) }, yAxis: { type: 'value', name: '秒' },
      series: [{ name: '平均时长', type: 'line', data: runDuration.value.map((r: any) => r.avg_duration_seconds), smooth: true, itemStyle: { color: '#E6A23C' } }],
    })
  }

  function renderStepLatencyChart() {
    if (!stepLatencyChartRef.value) return
    if (!stepLatencyChart) stepLatencyChart = echarts.init(stepLatencyChartRef.value)
    stepLatencyChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: stepLatency.value.map((r: any) => r.step_name), axisLabel: { rotate: 30 } }, yAxis: { type: 'value', name: '秒' },
      series: [{ name: '平均耗时', type: 'bar', data: stepLatency.value.map((r: any) => r.avg_duration_seconds), itemStyle: { color: '#F56C6C' } }],
    })
  }

  function renderCacheChart() {
    if (!cacheChartRef.value) return
    if (!cacheChart) cacheChart = echarts.init(cacheChartRef.value)
    cacheChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: cacheHitRate.value.map((r: any) => r.date) }, yAxis: { type: 'value', name: '%', max: 100 },
      series: [{ name: '命中率', type: 'line', data: cacheHitRate.value.map((r: any) => r.cache_hit_rate), smooth: true, areaStyle: { opacity: 0.3 }, itemStyle: { color: '#909399' } }],
    })
  }

  async function refreshAll() {
    await Promise.all([fetchOverview(), fetchTokenUsage(), fetchRunDuration(), fetchStepLatency(), fetchCacheHitRate(), fetchFmeaMetrics()])
    await nextTick()
    renderTokenChart(); renderDurationChart(); renderStepLatencyChart(); renderCacheChart()
  }

  function handleResize() { tokenChart?.resize(); durationChart?.resize(); stepLatencyChart?.resize(); cacheChart?.resize() }

  watch([projectId, days], () => { refreshAll() })

  onMounted(async () => { await fetchProjects(); await refreshAll(); window.addEventListener('resize', handleResize) })
  onUnmounted(() => { window.removeEventListener('resize', handleResize); tokenChart?.dispose(); durationChart?.dispose(); stepLatencyChart?.dispose(); cacheChart?.dispose() })

  return {
    projectId, days, projects, overviewCards, fmeaMetrics,
    tokenChartRef, durationChartRef, stepLatencyChartRef, cacheChartRef,
    goBack, refreshAll,
  }
}
