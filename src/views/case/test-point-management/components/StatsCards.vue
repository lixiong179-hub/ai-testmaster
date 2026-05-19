<template>
  <div class="stats-cards">
    <button
      class="stat-card"
      :class="{ 'is-active': !filters.priority }"
      type="button"
      @click="applyPriorityFilter(undefined)"
    >
      <span class="stat-caption">全部测试点</span>
      <span class="stat-value">{{ statsTotal }}</span>
      <span class="stat-label">当前筛选范围内总数</span>
    </button>
    <button
      class="stat-card high"
      :class="{ 'is-active': filters.priority === 1 }"
      type="button"
      @click="applyPriorityFilter(1)"
    >
      <span class="stat-caption">高优先级</span>
      <span class="stat-value">{{ highCount }}</span>
      <span class="stat-label">点击快速筛选高优先级</span>
    </button>
    <button
      class="stat-card medium"
      :class="{ 'is-active': filters.priority === 2 }"
      type="button"
      @click="applyPriorityFilter(2)"
    >
      <span class="stat-caption">中优先级</span>
      <span class="stat-value">{{ mediumCount }}</span>
      <span class="stat-label">适合常规回归与覆盖补齐</span>
    </button>
    <button
      class="stat-card low"
      :class="{ 'is-active': filters.priority === 3 }"
      type="button"
      @click="applyPriorityFilter(3)"
    >
      <span class="stat-caption">低优先级</span>
      <span class="stat-value">{{ lowCount }}</span>
      <span class="stat-label">可作为补充储备任务</span>
    </button>
    <div class="stat-card generated non-clickable">
      <span class="stat-caption">已生成用例</span>
      <span class="stat-value">{{ generatedCaseCount }}</span>
      <span class="stat-label">已绑定到测试用例的累计数量</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { TestPointMgmtKey } from '../useTestPointManagement'

const mgmt = inject(TestPointMgmtKey)!

const { statsTotal, highCount, mediumCount, lowCount, generatedCaseCount, filters, applyPriorityFilter } = mgmt
</script>

<style scoped>
.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 18px 16px;
  text-align: left;
  background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  border: 1px solid rgba(220, 230, 241, 0.95);
  border-radius: 18px;
  box-shadow: 0 8px 24px rgba(31, 45, 61, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
button.stat-card { width: 100%; cursor: pointer; }
button.stat-card:hover,
.stat-card.is-active {
  transform: translateY(-2px);
  border-color: rgba(64, 158, 255, 0.4);
  box-shadow: 0 16px 30px rgba(64, 158, 255, 0.12);
}
.stat-card.high { background: linear-gradient(180deg, #fff7f7 0%, #fff0f0 100%); }
.stat-card.medium { background: linear-gradient(180deg, #fffaf2 0%, #fdf4e5 100%); }
.stat-card.low { background: linear-gradient(180deg, #f8f9fc 0%, #f2f4f8 100%); }
.stat-card.generated { background: linear-gradient(180deg, #f4fff8 0%, #ebf8ef 100%); }
.stat-card.non-clickable { cursor: default; }
.stat-card.non-clickable:hover {
  transform: none;
  border-color: rgba(220, 230, 241, 0.95);
  box-shadow: 0 8px 24px rgba(31, 45, 61, 0.05);
}
.stat-caption { font-size: 13px; color: #7a8594; font-weight: 600; }
.stat-value { font-size: 30px; line-height: 1.1; font-weight: 700; color: #1f2d3d; }
.stat-label { color: #6b7684; font-size: 12px; line-height: 1.5; }
@media (max-width: 1280px) { .stats-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 960px) { .stats-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .stats-cards { grid-template-columns: 1fr; } }
</style>
