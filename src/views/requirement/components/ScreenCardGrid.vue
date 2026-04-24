<template>
  <div v-if="screens.length === 0 && !loading" class="empty-state">
    <el-empty description="暂无UI原型图片，请点击右上角上传">
      <el-button type="primary" @click="emit('addScreens')">上传图片</el-button>
    </el-empty>
  </div>

  <div v-else class="screen-grid">
    <UIScreenCard
      v-for="screen in screens"
      :key="screen.id"
      :screen="screen"
      :image-url="imageUrls[screen.id]"
      @click="emit('preview', screen)"
    >
      <template #actions>
        <el-button type="primary" size="small" link @click="emit('parse', screen)">
          解析
        </el-button>
        <el-button type="danger" size="small" link @click="emit('delete', screen)">
          删除
        </el-button>
      </template>
    </UIScreenCard>
  </div>
</template>

<script setup lang="ts">
import type { UIScreen } from '@/api/uiPrototype'
import UIScreenCard from '@/components/UIScreenCard.vue'

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
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}

@media (max-width: 768px) {
  .screen-grid {
    grid-template-columns: 1fr;
  }
}
</style>
