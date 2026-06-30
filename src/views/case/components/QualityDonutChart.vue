<template>
  <!-- Task11: 手写 SVG 环形图，避免引入新依赖；四色对应四种质量状态，点击扇区过滤 -->
  <div class="quality-donut-chart">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" class="donut-svg">
      <!-- 空数据时显示占位环 -->
      <circle
        v-if="total === 0"
        :cx="cx"
        :cy="cy"
        :r="r"
        fill="none"
        stroke="#e4e7ed"
        :stroke-width="strokeWidth"
      />
      <path
        v-for="seg in segments"
        :key="seg.status"
        :d="seg.path"
        :fill="seg.color"
        :class="[
          'donut-segment',
          { active: activeFilter === seg.status, dim: activeFilter && activeFilter !== seg.status },
        ]"
        @click="$emit('select', activeFilter === seg.status ? null : seg.status)"
      >
        <title>{{ seg.label }}: {{ seg.count }} 条</title>
      </path>
      <!-- 中心总数 -->
      <text :x="cx" :y="cy - 6" text-anchor="middle" class="donut-total">{{ total }}</text>
      <text :x="cx" :y="cy + 14" text-anchor="middle" class="donut-label">总用例</text>
    </svg>
    <div class="donut-legend">
      <div
        v-for="seg in segments"
        :key="seg.status"
        class="legend-item"
        :class="{
          active: activeFilter === seg.status,
          dim: activeFilter && activeFilter !== seg.status,
        }"
        @click="$emit('select', activeFilter === seg.status ? null : seg.status)"
      >
        <span class="legend-color" :style="{ background: seg.color }"></span>
        <span class="legend-text">{{ seg.label }}</span>
        <span class="legend-count">{{ seg.count }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QualityStatus } from '@/store/smartGeneration'

/** 质量分布环形图：手写 SVG 实现，无新依赖；扇区面积与数量成正比，点击过滤 */
const props = withDefaults(
  defineProps<{
    /** passed 数量 */
    passed: number
    /** warning 数量 */
    warning: number
    /** pending_review 数量 */
    pendingReview: number
    /** rejected 数量 */
    rejected: number
    /** 当前激活的过滤状态，null 表示无过滤 */
    activeFilter?: QualityStatus | null
    /** SVG 画布尺寸 */
    size?: number
  }>(),
  {
    activeFilter: null,
    size: 160,
  }
)

defineEmits<{
  (e: 'select', status: QualityStatus | null): void
}>()

const strokeWidth = 22
const r = computed(() => (props.size - strokeWidth) / 2)
const ir = computed(() => r.value - strokeWidth)
const cx = computed(() => props.size / 2)
const cy = computed(() => props.size / 2)

interface Segment {
  status: QualityStatus
  label: string
  color: string
  count: number
  path: string
}

const total = computed(() => props.passed + props.warning + props.pendingReview + props.rejected)

/** 极坐标转笛卡尔坐标（角度从 12 点位置顺时针，0°=正上方） */
function polar(cx: number, cy: number, radius: number, angleDeg: number): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)]
}

/** 构造环形扇区 path：外弧 + 内弧反向闭合 */
function describeArc(startAngle: number, endAngle: number): string {
  // 整圆特殊处理：避免 0° 与 360° 重合导致 path 为空
  const sweep = endAngle - startAngle
  if (sweep >= 360) {
    return [
      `M ${polar(cx.value, cy.value, r.value, 0)[0]} ${polar(cx.value, cy.value, r.value, 0)[1]}`,
      `A ${r.value} ${r.value} 0 1 1 ${polar(cx.value, cy.value, r.value, 180)[0]} ${polar(cx.value, cy.value, r.value, 180)[1]}`,
      `A ${r.value} ${r.value} 0 1 1 ${polar(cx.value, cy.value, r.value, 359.99)[0]} ${polar(cx.value, cy.value, r.value, 359.99)[1]}`,
      `L ${polar(cx.value, cy.value, ir.value, 359.99)[0]} ${polar(cx.value, cy.value, ir.value, 359.99)[1]}`,
      `A ${ir.value} ${ir.value} 0 1 0 ${polar(cx.value, cy.value, ir.value, 180)[0]} ${polar(cx.value, cy.value, ir.value, 180)[1]}`,
      `A ${ir.value} ${ir.value} 0 1 0 ${polar(cx.value, cy.value, ir.value, 0)[0]} ${polar(cx.value, cy.value, ir.value, 0)[1]}`,
      'Z',
    ].join(' ')
  }
  const [x1, y1] = polar(cx.value, cy.value, r.value, startAngle)
  const [x2, y2] = polar(cx.value, cy.value, r.value, endAngle)
  const [x3, y3] = polar(cx.value, cy.value, ir.value, endAngle)
  const [x4, y4] = polar(cx.value, cy.value, ir.value, startAngle)
  const largeArc = sweep > 180 ? 1 : 0
  return [
    `M ${x1} ${y1}`,
    `A ${r.value} ${r.value} 0 ${largeArc} 1 ${x2} ${y2}`,
    `L ${x3} ${y3}`,
    `A ${ir.value} ${ir.value} 0 ${largeArc} 0 ${x4} ${y4}`,
    'Z',
  ].join(' ')
}

const segments = computed<Segment[]>(() => {
  const items: { status: QualityStatus; label: string; color: string; count: number }[] = [
    { status: 'passed', label: '通过', color: '#67c23a', count: props.passed },
    { status: 'warning', label: '有轻微问题', color: '#e6a23c', count: props.warning },
    { status: 'pending_review', label: '需要确认', color: '#909399', count: props.pendingReview },
    { status: 'rejected', label: '不建议保存', color: '#f56c6c', count: props.rejected },
  ]
  if (total.value === 0) return []
  let angle = 0
  return items.map((it) => {
    const ratio = it.count / total.value
    const start = angle
    const end = angle + ratio * 360
    angle = end
    return { ...it, path: it.count > 0 ? describeArc(start, end) : '' }
  })
})
</script>

<style scoped>
.quality-donut-chart {
  display: flex;
  align-items: center;
  gap: 16px;
}
.donut-svg {
  flex-shrink: 0;
}
.donut-segment {
  cursor: pointer;
  transition:
    opacity 0.2s,
    transform 0.2s;
  transform-origin: center;
}
.donut-segment.dim {
  opacity: 0.35;
}
.donut-segment.active {
  opacity: 1;
}
.donut-total {
  font-size: 22px;
  font-weight: 700;
  fill: #303133;
}
.donut-label {
  font-size: 11px;
  fill: #909399;
}
.donut-legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 13px;
  transition: opacity 0.2s;
}
.legend-item.dim {
  opacity: 0.4;
}
.legend-item.active {
  background: #f5f7fa;
}
.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.legend-text {
  flex: 1;
  color: #606266;
}
.legend-count {
  font-weight: 600;
  color: #303133;
}
</style>
