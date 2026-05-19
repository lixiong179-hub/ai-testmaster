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
      <el-button type="primary" :icon="Refresh" @click="refreshAll" style="margin-left: 12px">刷新</el-button>
    </div>

    <el-row :gutter="16" class="overview-cards">
      <el-col :span="4" v-for="card in overviewCards" :key="card.key">
        <el-card shadow="hover" class="metric-card" :class="card.color">
          <div class="metric-title">{{ card.title }}</div>
          <div class="metric-value">{{ card.value }}<span class="metric-suffix">{{ card.suffix }}</span></div>
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
            <el-tag :type="row.count > 0 ? 'danger' : 'success'" size="small">{{ row.count > 0 ? '告警' : '正常' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { usePipelineDashboard } from './usePipelineDashboard'

const {
  projectId, days, projects, overviewCards, fmeaMetrics,
  tokenChartRef, durationChartRef, stepLatencyChartRef, cacheChartRef,
  goBack, refreshAll,
} = usePipelineDashboard()
void tokenChartRef; void durationChartRef; void stepLatencyChartRef; void cacheChartRef
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
.card-blue .metric-value { color: #409eff; }
.card-green .metric-value { color: #67c23a; }
.card-purple .metric-value { color: #9b59b6; }
.card-orange .metric-value { color: #e6a23c; }
.card-cyan .metric-value { color: #00bcd4; }
.card-teal .metric-value { color: #009688; }
.chart-container {
  width: 100%;
  height: 300px;
}
</style>
