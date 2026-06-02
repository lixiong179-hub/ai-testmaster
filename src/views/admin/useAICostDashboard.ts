import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { aiInvocationApi, usdToCny } from '@/api/aiInvocation'
import type {
  AIInvocationStatsItem,
  AIInvocationStatsParams,
  AIInvocationListItem,
} from '@/api/aiInvocation'
import ProjectAPI from '@/api/project'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

/** 格式化数字，添加千分位 */
function formatNumber(num: number): string {
  return num.toLocaleString('zh-CN')
}

/** 格式化人民币金额 */
function formatCny(num: number): string {
  if (num >= 10000) {
    return `${(num / 10000).toFixed(2)}万`
  }
  return num.toFixed(2)
}

export function useAICostDashboard() {
  const router = useRouter()
  const projectId = ref<number | undefined>(undefined)
  const days = ref(7)
  const loading = ref(false)
  const projects = ref<Array<{ id: number; name: string }>>([])

  // 概览数据
  const totalTokens = ref(0)
  const totalCostCny = ref(0)
  const totalCalls = ref(0)
  const successRate = ref(0)

  // 图表数据
  const modelStats = ref<AIInvocationStatsItem[]>([])
  const strategyStats = ref<AIInvocationStatsItem[]>([])
  const dateStats = ref<AIInvocationStatsItem[]>([])

  // 调用记录
  const invocationList = ref<AIInvocationListItem[]>([])
  const invocationTotal = ref(0)
  const invocationPage = ref(1)
  const invocationPageSize = ref(10)

  // 图表 DOM 引用
  const costTrendChartRef = ref<HTMLElement>()
  const tokenDailyChartRef = ref<HTMLElement>()
  const modelPieChartRef = ref<HTMLElement>()
  const strategyBarChartRef = ref<HTMLElement>()

  let costTrendChart: EChartsType | null = null
  let tokenDailyChart: EChartsType | null = null
  let modelPieChart: EChartsType | null = null
  let strategyBarChart: EChartsType | null = null

  /** 概览卡片 */
  const overviewCards = computed(() => [
    {
      key: 'tokens',
      title: '总 Token 消耗',
      value: formatNumber(totalTokens.value),
      suffix: '',
      color: 'card-blue',
    },
    {
      key: 'cost',
      title: '总成本',
      value: formatCny(totalCostCny.value),
      suffix: ' 元',
      color: 'card-orange',
    },
    {
      key: 'calls',
      title: '调用次数',
      value: formatNumber(totalCalls.value),
      suffix: ' 次',
      color: 'card-purple',
    },
    {
      key: 'success',
      title: '成功率',
      value: successRate.value.toFixed(1),
      suffix: '%',
      color: 'card-green',
    },
  ])

  const goBack = () => {
    router.back()
  }

  /** 获取项目列表 */
  async function fetchProjects() {
    try {
      const res = await ProjectAPI.getProjects({})
      projects.value = res?.data?.items ?? []
    } catch (e) {
      console.warn('获取项目列表失败:', e)
    }
  }

  /** 计算时间范围 */
  function getDateRange(): { start_date: string; end_date: string } {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - days.value + 1)
    return {
      start_date: start.toISOString().split('T')[0],
      end_date: end.toISOString().split('T')[0],
    }
  }

  /** 获取当前选中的项目ID（未选时默认第一个） */
  function getEffectiveProjectId(): number | undefined {
    if (projectId.value) return projectId.value
    if (projects.value.length > 0) return projects.value[0].id
    return undefined
  }

  /** 获取所有维度的统计数据 */
  async function fetchAllStats() {
    const pid = getEffectiveProjectId()
    if (!pid) return

    const dateRange = getDateRange()
    const paramsBase: AIInvocationStatsParams = {
      project_id: pid,
      ...dateRange,
    }

    loading.value = true
    try {
      const [modelRes, strategyRes, dateRes] = await Promise.all([
        aiInvocationApi.getStats({ ...paramsBase, group_by: 'model' }),
        aiInvocationApi.getStats({ ...paramsBase, group_by: 'strategy' }),
        aiInvocationApi.getStats({ ...paramsBase, group_by: 'date' }),
      ])

      modelStats.value = modelRes.data?.items ?? []
      strategyStats.value = strategyRes.data?.items ?? []
      dateStats.value = dateRes.data?.items ?? []

      // 计算概览数据
      computeOverview()
    } catch (e) {
      console.warn('获取统计数据失败:', e)
    } finally {
      loading.value = false
    }
  }

  /** 根据各维度数据计算概览 */
  function computeOverview() {
    const items = dateStats.value
    totalTokens.value = items.reduce(
      (sum: number, r: AIInvocationStatsItem) =>
        sum + r.total_prompt_tokens + r.total_completion_tokens,
      0
    )
    totalCostCny.value = usdToCny(
      items.reduce(
        (sum: number, r: AIInvocationStatsItem) => sum + r.total_cost_usd,
        0
      )
    )
    totalCalls.value = items.reduce(
      (sum: number, r: AIInvocationStatsItem) => sum + r.total_calls,
      0
    )
    // 成功率从调用记录中统计
    successRate.value = totalCalls.value > 0 ? 100 : 0
  }

  /** 获取调用记录（用于成功率计算和列表展示） */
  async function fetchInvocationList() {
    const pid = getEffectiveProjectId()
    if (!pid) return

    try {
      const res = await aiInvocationApi.getList({
        project_id: pid,
        page: invocationPage.value,
        page_size: invocationPageSize.value,
      })
      const data = res.data
      invocationList.value = data?.items ?? []
      invocationTotal.value = data?.total ?? 0

      // 统计成功率
      if (invocationList.value.length > 0) {
        const successCount = invocationList.value.filter(
          (item) => item.status === 'success'
        ).length
        successRate.value =
          invocationTotal.value > 0
            ? (successCount / invocationList.value.length) * 100
            : 0
      }
    } catch (e) {
      console.warn('获取调用记录失败:', e)
    }
  }

  /** 渲染成本趋势图（按日期） */
  function renderCostTrendChart() {
    if (!costTrendChartRef.value) return
    if (!costTrendChart) {
      costTrendChart = echarts.init(costTrendChartRef.value)
    }
    const sorted = [...dateStats.value].sort((a, b) =>
      a.group_key.localeCompare(b.group_key)
    )
    costTrendChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const p = Array.isArray(params) ? params : [params]
          const date = (p[0] as { axisValue?: string })?.axisValue ?? ''
          let html = `${date}<br/>`
          p.forEach((item: unknown) => {
            const s = item as { seriesName?: string; value?: number; marker?: string }
            html += `${s.marker ?? ''} ${s.seriesName ?? ''}: ${s.value?.toFixed(4) ?? '-'} 元<br/>`
          })
          return html
        },
      },
      legend: { data: ['成本（元）'] },
      grid: { left: 60, right: 20, bottom: 30, top: 40 },
      xAxis: {
        type: 'category',
        data: sorted.map((r: AIInvocationStatsItem) => r.group_key),
        axisLabel: { rotate: 30 },
      },
      yAxis: { type: 'value', name: '元' },
      series: [
        {
          name: '成本（元）',
          type: 'line',
          data: sorted.map((r: AIInvocationStatsItem) => usdToCny(r.total_cost_usd)),
          smooth: true,
          areaStyle: { opacity: 0.2 },
          itemStyle: { color: '#E6A23C' },
        },
      ],
    })
  }

  /** 渲染每日 Token 消耗图 */
  function renderTokenDailyChart() {
    if (!tokenDailyChartRef.value) return
    if (!tokenDailyChart) {
      tokenDailyChart = echarts.init(tokenDailyChartRef.value)
    }
    const sorted = [...dateStats.value].sort((a, b) =>
      a.group_key.localeCompare(b.group_key)
    )
    tokenDailyChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['Prompt Tokens', 'Completion Tokens'] },
      grid: { left: 60, right: 20, bottom: 30, top: 40 },
      xAxis: {
        type: 'category',
        data: sorted.map((r: AIInvocationStatsItem) => r.group_key),
        axisLabel: { rotate: 30 },
      },
      yAxis: { type: 'value' },
      series: [
        {
          name: 'Prompt Tokens',
          type: 'bar',
          stack: 'tokens',
          data: sorted.map((r: AIInvocationStatsItem) => r.total_prompt_tokens),
          itemStyle: { color: '#409EFF' },
        },
        {
          name: 'Completion Tokens',
          type: 'bar',
          stack: 'tokens',
          data: sorted.map((r: AIInvocationStatsItem) => r.total_completion_tokens),
          itemStyle: { color: '#67C23A' },
        },
      ],
    })
  }

  /** 渲染模型成本饼图 */
  function renderModelPieChart() {
    if (!modelPieChartRef.value) return
    if (!modelPieChart) {
      modelPieChart = echarts.init(modelPieChartRef.value)
    }
    const pieData = modelStats.value.map((r: AIInvocationStatsItem) => ({
      name: r.group_key,
      value: Number(usdToCny(r.total_cost_usd).toFixed(4)),
    }))
    modelPieChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const p = params as { name?: string; value?: number; percent?: number }
          return `${p.name ?? ''}: ${p.value?.toFixed(4) ?? '-'} 元 (${p.percent ?? 0}%)`
        },
      },
      legend: { orient: 'vertical', left: 'left', top: 'middle' },
      series: [
        {
          name: '模型成本',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['60%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}: {d}%' },
          data: pieData,
        },
      ],
    })
  }

  /** 渲染策略成本柱状图 */
  function renderStrategyBarChart() {
    if (!strategyBarChartRef.value) return
    if (!strategyBarChart) {
      strategyBarChart = echarts.init(strategyBarChartRef.value)
    }
    strategyBarChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const p = Array.isArray(params) ? params : [params]
          const name = (p[0] as { axisValue?: string })?.axisValue ?? ''
          let html = `${name}<br/>`
          p.forEach((item: unknown) => {
            const s = item as { seriesName?: string; value?: number; marker?: string }
            html += `${s.marker ?? ''} ${s.seriesName ?? ''}: ${s.value?.toFixed(4) ?? '-'} 元<br/>`
          })
          return html
        },
      },
      grid: { left: 60, right: 20, bottom: 30, top: 20 },
      xAxis: {
        type: 'category',
        data: strategyStats.value.map((r: AIInvocationStatsItem) => r.group_key),
        axisLabel: { rotate: 30 },
      },
      yAxis: { type: 'value', name: '元' },
      series: [
        {
          name: '成本（元）',
          type: 'bar',
          data: strategyStats.value.map((r: AIInvocationStatsItem) =>
            usdToCny(r.total_cost_usd)
          ),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#9b59b6' },
              { offset: 1, color: '#c39bd3' },
            ]),
          },
        },
      ],
    })
  }

  /** 刷新所有数据并重绘图表 */
  async function refreshAll() {
    await fetchAllStats()
    await fetchInvocationList()
    await nextTick()
    renderCostTrendChart()
    renderTokenDailyChart()
    renderModelPieChart()
    renderStrategyBarChart()
  }

  /** 窗口大小变化时自适应 */
  function handleResize() {
    costTrendChart?.resize()
    tokenDailyChart?.resize()
    modelPieChart?.resize()
    strategyBarChart?.resize()
  }

  /** 调用记录分页变化 */
  async function handlePageChange(page: number) {
    invocationPage.value = page
    await fetchInvocationList()
  }

  watch([projectId, days], () => {
    invocationPage.value = 1
    refreshAll()
  })

  onMounted(async () => {
    await fetchProjects()
    await refreshAll()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    costTrendChart?.dispose()
    tokenDailyChart?.dispose()
    modelPieChart?.dispose()
    strategyBarChart?.dispose()
  })

  return {
    projectId,
    days,
    loading,
    projects,
    overviewCards,
    invocationList,
    invocationTotal,
    invocationPage,
    invocationPageSize,
    costTrendChartRef,
    tokenDailyChartRef,
    modelPieChartRef,
    strategyBarChartRef,
    goBack,
    refreshAll,
    handlePageChange,
  }
}
