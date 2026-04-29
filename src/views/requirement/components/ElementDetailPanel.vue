<template>
  <el-collapse-item name="elements">
    <template #title>
      <div class="collapse-title">
        <el-icon><Grid /></el-icon>
        <span>元素详情</span>
        <el-tag size="small" type="info">{{ elements.length }}项</el-tag>
      </div>
    </template>
    <div class="elements-list">
      <div
        v-for="(element, index) in sortedElements"
        :key="index"
        class="element-item"
      >
        <div class="element-main">
          <el-tag
            :type="getElementTypeColor(element.type)"
            size="small"
            class="element-type-tag"
          >
            <el-icon v-if="element.type === 'button'"><Pointer /></el-icon>
            <el-icon v-else-if="element.type === 'input'"><Edit /></el-icon>
            <el-icon v-else-if="element.type === 'icon'"><Star /></el-icon>
            <el-icon v-else-if="element.type === 'link'"><Link /></el-icon>
            <el-icon v-else-if="element.type === 'text'"><Document /></el-icon>
            <el-icon v-else><Box /></el-icon>
            {{ element.type }}
          </el-tag>
          <span class="element-label">{{ element.label }}</span>
          <el-tag v-if="element.semantic_hint" size="small" type="info">{{ element.semantic_hint }}</el-tag>
        </div>
        <div class="element-meta" v-if="element.description">
          <span class="element-desc">{{ element.description }}</span>
          <span class="element-position" v-if="element.position">
            位置: ({{ element.position.x }}, {{ element.position.y }})
            <span v-if="element.position.width">尺寸: {{ element.position.width }}x{{ element.position.height }}</span>
          </span>
          <el-tag v-if="element.interactive" size="small" type="success">可交互</el-tag>
          <el-tag v-if="element.state" size="small" type="warning">{{ element.state }}</el-tag>
        </div>
      </div>
    </div>
  </el-collapse-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Grid, Pointer, Edit, Star, Link, Document, Box } from '@element-plus/icons-vue'
import type { UIElement } from '@/api/uiPrototype'

const props = defineProps<{
  elements: UIElement[]
}>()

const getElementTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    button: 'primary', input: 'warning', text: 'info', icon: '',
    link: '', image: 'success', container: 'info', navigation: '',
    list_item: '', checkbox: 'success', radio: 'success', switch: 'success',
    slider: 'warning', form: 'primary', dropdown: 'warning', video: 'danger'
  }
  return colorMap[type] || 'info'
}

const sortedElements = computed(() => {
  if (!props.elements) return []
  return [...props.elements].sort((a, b) => {
    const posA = a.position || { y: 0, x: 0 }
    const posB = b.position || { y: 0, x: 0 }
    if (posA.y !== posB.y) return posA.y - posB.y
    return posA.x - posB.x
  })
})
</script>

<style scoped>
.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.elements-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.element-item {
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.element-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.element-type-tag {
  text-transform: capitalize;
}

.element-label {
  font-weight: 500;
  color: #303133;
}

.element-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}

.element-position {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
