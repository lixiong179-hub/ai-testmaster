<template>
  <div class="ab-test-dashboard">
    <el-page-header @back="goBack" title="返回" content="A/B 实验看板" />

    <div class="dashboard-filters">
      <el-select
        v-model="experimentId"
        placeholder="选择实验"
        filterable
        clearable
        style="width: 360px"
        :loading="loading"
      >
        <el-option
          v-for="exp in experiments"
          :key="exp.experiment_id"
          :label="`${exp.experiment_id}（样本 ${exp.sample_count}）`"
          :value="exp.experiment_id"
        />
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

    <el-empty v-if="!loading && !hasData" description="暂无实验数据" />

    <template v-else>
      <!-- 变体概览卡片 -->
      <el-row :gutter="16" class="overview-cards">
        <el-col :span="6" v-for="card in variantOverviewCards" :key="card.key">
          <el-card shadow="hover" class="metric-card" :class="card.color">
            <div class="metric-title">{{ card.title }}</div>
            <div class="metric-value">
              {{ card.value }}<span class="metric-suffix">{{ card.suffix }}</span>
            </div>
            <div class="metric-sub">{{ card.sub }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 指标对比表 -->
      <el-card shadow="hover" style="margin-top: 16px">
        <template #header><span>指标对比（control vs treatment）</span></template>
        <el-table :data="comparisonRows" stripe v-loading="loading" style="width: 100%">
          <el-table-column prop="label" label="指标" min-width="150" />
          <el-table-column label="优化方向" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.direction === 'higher' ? 'success' : 'warning'">
                {{ row.direction === 'higher' ? '越高越好' : '越低越好' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Control 均值" width="140" align="right">
            <template #default="{ row }">
              {{ row.controlMean !== null ? formatValue(row.controlMean) : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="Treatment 均值" width="140" align="right">
            <template #default="{ row }">
              {{ row.treatmentMean !== null ? formatValue(row.treatmentMean) : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="差异(%)" width="120" align="right">
            <template #default="{ row }">
              <span v-if="row.diffPercent === null">-</span>
              <span v-else :class="row.improved ? 'diff-improved' : 'diff-regressed'">
                {{ row.diffPercent > 0 ? '+' : '' }}{{ row.diffPercent }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="样本数 (C/T)" width="130" align="right">
            <template #default="{ row }">
              {{ row.controlSample }} / {{ row.treatmentSample }}
            </template>
          </el-table-column>
          <el-table-column label="差异可视化" min-width="200">
            <template #default="{ row }">
              <div class="diff-bar-wrapper" v-if="row.diffPercent !== null">
                <div
                  class="diff-bar"
                  :class="row.improved ? 'bar-improved' : 'bar-regressed'"
                  :style="{ width: diffBarWidth(row.diffPercent) + '%' }"
                />
                <span class="diff-bar-label">
                  {{ row.improved ? '改善' : '回退' }}
                </span>
              </div>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 实验信息 -->
      <el-card shadow="hover" style="margin-top: 16px" v-if="summary">
        <template #header><span>实验信息</span></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="实验 ID">
            {{ summary.experiment_id }}
          </el-descriptions-item>
          <el-descriptions-item label="变体数量">
            {{ Object.keys(summary.variants ?? {}).length }}
          </el-descriptions-item>
          <el-descriptions-item
            v-for="item in variantMetaList"
            :key="item.variant"
            :label="`变体 ${item.variant} 指标数`"
          >
            {{ item.metricCount }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useAbTestDashboard } from './useAbTestDashboard'
import type { AbTestVariantStats } from '@/api/abTest'

const {
  loading,
  experiments,
  experimentId,
  summary,
  comparisonRows,
  hasData,
  goBack,
  refreshAll,
} = useAbTestDashboard()

/** 变体元信息列表：用于 el-descriptions 遍历展示各变体指标数 */
const variantMetaList = computed(() => {
  const variants = summary.value?.variants ?? {}
  return Object.keys(variants).map((variant) => ({
    variant,
    metricCount: Object.keys(variants[variant] ?? {}).length,
  }))
})

/** 变体概览卡片：control/treatment 样本规模、改善与回退指标数 */
const variantOverviewCards = computed(() => {
  const variants = summary.value?.variants ?? {}
  const control = variants['control'] ?? {}
  const treatment = variants['treatment'] ?? {}
  const improvedCount = comparisonRows.value.filter((r) => r.improved === true).length
  const regressedCount = comparisonRows.value.filter((r) => r.improved === false).length
  const totalMetrics = comparisonRows.value.length
  return [
    {
      key: 'control-sample',
      title: 'Control 样本规模',
      value: variantSampleCount(control),
      suffix: '',
      sub: `${Object.keys(control).length} 项指标`,
      color: 'card-blue',
    },
    {
      key: 'treatment-sample',
      title: 'Treatment 样本规模',
      value: variantSampleCount(treatment),
      suffix: '',
      sub: `${Object.keys(treatment).length} 项指标`,
      color: 'card-green',
    },
    {
      key: 'improved-count',
      title: '改善指标数',
      value: improvedCount,
      suffix: ` / ${totalMetrics}`,
      sub: 'treatment 优于 control',
      color: 'card-purple',
    },
    {
      key: 'regressed-count',
      title: '回退指标数',
      value: regressedCount,
      suffix: ` / ${totalMetrics}`,
      sub: 'treatment 劣于 control',
      color: 'card-orange',
    },
  ]
})

/** 统计某变体的样本规模（取该变体下各指标样本数的最大值） */
function variantSampleCount(stats: AbTestVariantStats): number {
  const values = Object.values(stats) as Array<{ sample_count: number }>
  if (values.length === 0) return 0
  return Math.max(...values.map((v) => v.sample_count || 0))
}

/** 格式化指标值：整数直返，率类保留 4 位小数 */
function formatValue(val: number): string {
  if (Number.isInteger(val)) return val.toString()
  return val.toFixed(4)
}

/** 差异可视化条宽度：按绝对值映射，50% 差异对应满宽 */
function diffBarWidth(diffPercent: number): number {
  const abs = Math.abs(diffPercent)
  return Math.min(100, Math.round(abs * 2))
}
</script>

<style scoped>
.ab-test-dashboard {
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
  color: var(--color-info);
  margin-bottom: 8px;
}
.metric-value {
  font-size: 26px;
  font-weight: 700;
}
.metric-suffix {
  font-size: 13px;
  font-weight: 400;
  color: var(--color-info);
}
.metric-sub {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 6px;
}
.card-blue .metric-value {
  color: var(--color-primary);
}
.card-green .metric-value {
  color: var(--color-success);
}
.card-purple .metric-value {
  color: #9b59b6;
}
.card-orange .metric-value {
  color: var(--color-warning);
}
.diff-improved {
  color: var(--color-success);
  font-weight: 600;
}
.diff-regressed {
  color: var(--color-danger);
  font-weight: 600;
}
.diff-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}
.diff-bar {
  height: 10px;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.bar-improved {
  background: var(--color-success);
}
.bar-regressed {
  background: var(--color-danger);
}
.diff-bar-label {
  font-size: 12px;
  color: var(--color-info);
  white-space: nowrap;
}
</style>
