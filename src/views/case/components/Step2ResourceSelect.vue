<template>
  <div class="step-content">
    <div class="step-title">
      <el-icon><Document /></el-icon>
      <span>选择需求资源</span>
    </div>
    <div class="step-body">
      <div class="filter-bar">
        <el-radio-group v-model="resourceTypeFilter" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="requirement">需求文档</el-radio-button>
          <el-radio-button value="ui_mockup">UI原型</el-radio-button>
          <el-radio-button value="api_doc">API文档</el-radio-button>
        </el-radio-group>
      </div>

      <div v-if="filteredResourceRows.length > 0" class="resource-list">
        <div
          v-for="resource in filteredResourceRows"
          :key="resource.id"
          class="resource-item"
          :class="{ active: selectedResource?.id === resource.id }"
          @click="handleResourceSelect(resource)"
        >
          <div class="resource-icon">
            <el-icon :size="24">
              <component :is="getResourceIcon(resource.resource_type)" />
            </el-icon>
          </div>
          <div class="resource-info">
            <div class="resource-name">{{ resource.display_name }}</div>
            <div class="resource-meta">
              <el-tag size="small" :type="getResourceTypeTagType(resource.resource_type)">
                {{ getResourceTypeLabel(resource.resource_type) }}
              </el-tag>
              <span class="resource-size">{{ resource.size_text }}</span>
              <span class="resource-time">{{ resource.time_text }}</span>
            </div>
          </div>
          <div class="resource-action">
            <el-button type="primary" size="small" @click.stop="goToExtract(resource)">
              提取测试点
            </el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-hint">
        <el-empty description="该项目暂无上传文件，请先在「资源管理」中添加" :image-size="120" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import { useTestPointExtract } from '@/composables/useTestPointExtract'

const {
  resourceTypeFilter,
  filteredResourceRows,
  selectedResource,
  handleResourceSelect,
  getResourceIcon,
  getResourceTypeTagType,
  getResourceTypeLabel,
  goToExtract,
} = useTestPointExtract()
</script>
