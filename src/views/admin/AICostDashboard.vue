<template>
  <div class="ai-cost-dashboard">
    <el-page-header @back="goBack" title="返回" content="AI 成本仪表盘" />

    <div class="dashboard-filters">
      <el-select
        v-model="projectId"
        placeholder="全部项目"
        clearable
        style="width: 200px"
      >
        <el-option
          v-for="p in projects"
          :key="p.id"
          :label="p.name"
          :value="p.id"
        />
      </el-select>
      <el-select v-model="days" style="width: 120px; margin-left: 12px">
        <el-option label="近7天" :value="7" />
        <el-option label="近14天" :value="14" />
        <el-option label="近30天" :value="30" />
      </el-select>
      <el-button
        type="primary"
        :icon="Refresh"
        :loading="loading"
        @click="refreshAll"
        style="margin-left: 12px"
      >
        刷新
      </el-button>
    </div>

    <el-row :gutter="16" class="overview-cards">
      <el-col :span="6" v-for="card in overviewCards" :key="card.key">
        <el-card shadow="hover" class="metric-card" :class="card.color">
          <div class="metric-title">{{ card.title }}</div>
          <div class="metric-value">
            {{ card.value
            }}<span class="metric-suffix">{{ card.suffix }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>成本趋势（元）</span></template>
          <div :ref="setCostTrendChartRef" class="chart-container" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>每日 Token 消耗</span></template>
          <div :ref="setTokenDailyChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>模型成本分布（元）</span></template>
          <div :ref="setModelPieChartRef" class="chart-container" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>策略成本对比（元）</span></template>
          <div :ref="setStrategyBarChartRef" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 16px">
      <template #header><span>调用记录明细</span></template>
      <el-table :data="invocationList" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column prop="step_name" label="Step" width="140" />
        <el-table-column prop="prompt_tokens" label="Prompt Tokens" width="130" align="right" />
        <el-table-column
          prop="completion_tokens"
          label="Completion Tokens"
          width="160"
          align="right"
        />
        <el-table-column label="成本（元）" width="120" align="right">
          <template #default="{ row }">
            {{ formatCost(row.cost_usd) }}
          </template>
        </el-table-column>
        <el-table-column prop="latency_ms" label="耗时(ms)" width="100" align="right" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'success' ? 'success' : 'danger'"
              size="small"
            >
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generation_strategy" label="策略" width="120" />
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrapper" v-if="invocationTotal > 0">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="invocationTotal"
          :page-size="invocationPageSize"
          :current-page="invocationPage"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { useAICostDashboard } from './useAICostDashboard'
import { usdToCny } from '@/api/aiInvocation'

const {
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
} = useAICostDashboard()

const asHtmlElement = (el: unknown): HTMLElement | undefined =>
  el instanceof HTMLElement ? el : undefined

const setCostTrendChartRef = (el: unknown) => {
  costTrendChartRef.value = asHtmlElement(el)
}
const setTokenDailyChartRef = (el: unknown) => {
  tokenDailyChartRef.value = asHtmlElement(el)
}
const setModelPieChartRef = (el: unknown) => {
  modelPieChartRef.value = asHtmlElement(el)
}
const setStrategyBarChartRef = (el: unknown) => {
  strategyBarChartRef.value = asHtmlElement(el)
}

/** 格式化成本为人民币元 */
function formatCost(costUsd: number): string {
  return usdToCny(costUsd).toFixed(4)
}

/** 格式化时间 */
function formatTime(timeStr: string): string {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  if (isNaN(d.getTime())) return timeStr
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>

<style scoped>
.ai-cost-dashboard {
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
.chart-container {
  width: 100%;
  height: 300px;
}
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
