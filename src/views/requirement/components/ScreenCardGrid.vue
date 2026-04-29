<template>
  <div v-if="screens.length === 0 && !loading" class="empty-state">
    <el-empty description="暂无UI原型图片，请点击右上角上传">
      <el-button type="primary" @click="emit('addScreens')">上传图片</el-button>
    </el-empty>
  </div>

  <div v-else class="screen-grid">
    <div
      v-for="screen in screens"
      :key="screen.id"
      class="screen-card"
      @click="emit('preview', screen)"
    >
      <div class="screen-image-wrapper">
        <img
          v-if="screen.original_file_path && imageUrls[screen.id]"
          :src="imageUrls[screen.id]"
          :alt="screen.screen_name"
          class="screen-image"
          loading="lazy"
        />
        <div v-else class="screen-image-placeholder">
          <el-icon :size="40"><Picture /></el-icon>
        </div>
        <div class="screen-overlay">
          <el-tag
            :type="getParseStatusType(screen.parse_status)"
            size="small"
            class="parse-status-tag"
          >
            {{ screen.parse_status_text || getParseStatusText(screen.parse_status) }}
          </el-tag>
        </div>
      </div>
      <div class="screen-info">
        <div class="screen-name" :title="screen.screen_name">{{ screen.screen_name }}</div>
        <div class="screen-meta">
          <span v-if="screen.element_count">{{ screen.element_count }}个元素</span>
          <span v-if="screen.button_count">{{ screen.button_count }}个按钮</span>
        </div>
      </div>
      <div class="screen-actions" @click.stop>
        <el-button type="primary" size="small" link @click="emit('parse', screen)">
          解析
        </el-button>
        <el-button type="danger" size="small" link @click="emit('delete', screen)">
          删除
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Picture } from '@element-plus/icons-vue'
import type { UIScreen } from '@/api/uiPrototype'
import { getParseStatusType, getParseStatusText } from '@/composables/useParseStatus'

defineProps<{
  screens: UIScreen[]
  imageUrls: Record<number, string>
  loading: boolean
}>()

const emit = defineEmits<{
  preview: [screen: UIScreen]
  parse: [screen: UIScreen]
  delete: [screen: UIScreen]
  addScreens: []
}>()
</script>

<style scoped>
.empty-state {
  padding: 60px 0;
}

.screen-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
}

.screen-card {
  border: 1px solid #e8ecf0;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #ffffff;
}

.screen-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-4px);
  border-color: #d0d7de;
}

.screen-image-wrapper {
  position: relative;
  width: 100%;
  height: 185px;
  background: linear-gradient(145deg, #f8f9fb 0%, #e8ecf0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.screen-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.screen-image-placeholder {
  color: #a0a8b4;
}

.screen-overlay {
  position: absolute;
  top: 10px;
  right: 10px;
}

.parse-status-tag {
  backdrop-filter: blur(6px);
  border-radius: 6px;
}

.screen-info {
  padding: 14px 16px;
}

.screen-name {
  font-size: 15px;
  font-weight: 500;
  color: #1a1d21;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 8px;
}

.screen-meta {
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  gap: 12px;
}

.screen-actions {
  padding: 0 16px 14px;
  display: flex;
  gap: 12px;
}
</style>
