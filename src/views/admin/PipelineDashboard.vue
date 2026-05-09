<template>
  <div class="pipeline-dashboard">
    <el-page-header @back="goBack" title="返回" content="Pipeline 成本与性能仪表盘" />

    <div class="dashboard-filters">
      <el-select v-model="projectId" placeholder="全部项目" clearable style="width: 200px">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="days" style="width: 120px; margin-left: 12px">
        <el-option label="近7天" :value="7" />
        <el-option label="近14天" :value="14" />
        <el-option label="近30天" :value="30" />
      </el-select>
      <el-button type="primary" :icon="Refresh" @click="refreshAll" style="margin-left: 12px"
        >刷新</el-button
      >
    </div>

    <el-row :gutter="16" class="overview-cards">
      <el-col :span="4" v-for="card in overviewCards" :key="card.key">
        <el-card shadow="hover" class="metric-card" :class="card.color">
          <div class="metric-title">{{ card.title }}</div>
          <div class="metric-value">
            {{ card.value }}<span class="metric-suffix">{{ card.suffix }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>每日 Token 消耗</span></template>
          <div ref="tokenChartRef" class="chart-container" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>平均运行时长 (秒)</span></template>
          <div ref="durationChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>各 Step 耗时分布</span></template>
          <div ref="stepLatencyChartRef" class="chart-container" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>缓存命中率 (%)</span></template>
          <div ref="cacheChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 16px">
      <template #header><span>FMEA 监控指标</span></template>
      <el-table :data="fmeaMetrics" stripe style="width: 100%">
        <el-table-column prop="fmea_id" label="FMEA ID" width="100" />
        <el-table-column prop="metric_name" label="指标名" width="200" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="count" label="次数" width="100" />
        <el-table-column prop="total" label="总值" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.count > 0 ? 'danger' : 'success'" size="small">
              {{ row.count > 0 ? '告警' : '正常' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as echarts from 'echarts'

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

function goBack() {
  router.back()
}

async function fetchProjects() {
  try {
    const res = await request.get('/api/v1/project/list')
    projects.value = res.data?.data?.items ?? res.data?.items ?? []
  } catch (e) {
    console.warn('获取项目列表失败:', e)
  }
}

async function fetchOverview() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/dashboard/overview', { params })
    overview.value = res.data?.data ?? {}
  } catch (e) {
    console.warn('获取总览失败:', e)
  }
}

async function fetchTokenUsage() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/dashboard/token-usage', { params })
    tokenUsage.value = res.data?.data ?? []
  } catch (e) {
    console.warn('获取Token消耗失败:', e)
  }
}

async function fetchRunDuration() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/dashboard/run-duration', { params })
    runDuration.value = res.data?.data ?? []
  } catch (e) {
    console.warn('获取运行时长失败:', e)
  }
}

async function fetchStepLatency() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/dashboard/step-latency', { params })
    stepLatency.value = res.data?.data ?? []
  } catch (e) {
    console.warn('获取Step耗时失败:', e)
  }
}

async function fetchCacheHitRate() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/dashboard/cache-hit-rate', { params })
    cacheHitRate.value = res.data?.data ?? []
  } catch (e) {
    console.warn('获取缓存命中率失败:', e)
  }
}

async function fetchFmeaMetrics() {
  try {
    const params: Record<string, any> = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await request.get('/api/v1/pipeline/metrics/summary', { params })
    fmeaMetrics.value = res.data?.data?.metrics ?? []
  } catch (e) {
    console.warn('获取FMEA指标失败:', e)
  }
}

function renderTokenChart() {
  if (!tokenChartRef.value) return
  if (!tokenChart) tokenChart = echarts.init(tokenChartRef.value)
  const dates = tokenUsage.value.map((r: any) => r.date)
  const promptTokens = tokenUsage.value.map((r: any) => r.prompt_tokens)
  const completionTokens = tokenUsage.value.map((r: any) => r.completion_tokens)
  tokenChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Prompt Tokens', 'Completion Tokens'] },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Prompt Tokens',
        type: 'bar',
        stack: 'tokens',
        data: promptTokens,
        itemStyle: { color: '#409EFF' },
      },
      {
        name: 'Completion Tokens',
        type: 'bar',
        stack: 'tokens',
        data: completionTokens,
        itemStyle: { color: '#67C23A' },
      },
    ],
  })
}

function renderDurationChart() {
  if (!durationChartRef.value) return
  if (!durationChart) durationChart = echarts.init(durationChartRef.value)
  const dates = runDuration.value.map((r: any) => r.date)
  const avgDurations = runDuration.value.map((r: any) => r.avg_duration_seconds)
  durationChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '秒' },
    series: [
      {
        name: '平均时长',
        type: 'line',
        data: avgDurations,
        smooth: true,
        itemStyle: { color: '#E6A23C' },
      },
    ],
  })
}

function renderStepLatencyChart() {
  if (!stepLatencyChartRef.value) return
  if (!stepLatencyChart) stepLatencyChart = echarts.init(stepLatencyChartRef.value)
  const names = stepLatency.value.map((r: any) => r.step_name)
  const avgDurations = stepLatency.value.map((r: any) => r.avg_duration_seconds)
  stepLatencyChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '秒' },
    series: [
      { name: '平均耗时', type: 'bar', data: avgDurations, itemStyle: { color: '#F56C6C' } },
    ],
  })
}

function renderCacheChart() {
  if (!cacheChartRef.value) return
  if (!cacheChart) cacheChart = echarts.init(cacheChartRef.value)
  const dates = cacheHitRate.value.map((r: any) => r.date)
  const rates = cacheHitRate.value.map((r: any) => r.cache_hit_rate)
  cacheChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '%', max: 100 },
    series: [
      {
        name: '命中率',
        type: 'line',
        data: rates,
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

watch([projectId, days], () => {
  refreshAll()
})

onMounted(async () => {
  await fetchProjects()
  await refreshAll()
  window.addEventListener('resize', () => {
    tokenChart?.resize()
    durationChart?.resize()
    stepLatencyChart?.resize()
    cacheChart?.resize()
  })
})
</script>

<style scoped>
.pipeline-dashboard {
  padding: 20px;
}
.dashboard-filters {
  display: flex;
  align-items: center;
  margin: 16px 0;
}
.overview-cards {
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
  padding: 12px;
}
.metric-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
}
.metric-suffix {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
}
.card-blue .metric-value {
  color: #409eff;
}
.card-green .metric-value {
  color: #67c23a;
}
.card-purple .metric-value {
  color: #9b59b6;
}
.card-orange .metric-value {
  color: #e6a23c;
}
.card-cyan .metric-value {
  color: #00bcd4;
}
.card-teal .metric-value {
  color: #009688;
}
.chart-container {
  width: 100%;
  height: 300px;
}
</style>
