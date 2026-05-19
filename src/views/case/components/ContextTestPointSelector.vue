<template>
  <el-form-item label="测试点">
    <div class="test-point-selector" :class="{ 'has-data': store.testPointTotal > 0 }">
      <div class="tp-toolbar" v-if="store.testPointTotal > 0 || store.formData.test_point_ids.length > 0">
        <div class="tp-toolbar-left">
          <span class="tp-stat" v-if="store.testPointTotal > 0">共 <strong>{{ store.testPointTotal }}</strong> 条</span>
          <el-tag size="small" type="primary" effect="dark" v-if="store.formData.test_point_ids.length > 0">已选 {{ store.formData.test_point_ids.length }}</el-tag>
        </div>
        <div class="tp-toolbar-right">
          <el-button link type="primary" size="small" @mousedown.prevent @click.stop.prevent="store.selectAllTestPoints" :disabled="store.testPointAllIds.length === 0">全选</el-button>
          <el-button link type="danger" size="small" @mousedown.prevent @click.stop.prevent="store.deselectAllTestPoints" :disabled="store.formData.test_point_ids.length === 0">清空</el-button>
        </div>
      </div>
      <el-select :key="store.testPointSelectKey" v-model="store.formData.test_point_ids" multiple filterable placeholder="点击选择或搜索测试点（可选，不选则使用手动输入）" class="tp-select" popper-class="tp-dropdown" collapse-tags collapse-tags-tooltip :max-collapse-tags="2">
        <template #header>
          <div class="tp-d-header" @mousedown.prevent>
            <div class="tp-d-search"><el-icon><Search /></el-icon><input placeholder="搜索..." /></div>
            <div class="tp-d-info">
              <span>{{ store.testPointPage }}/{{ Math.ceil(store.testPointTotal / store.testPointPageSize) || 1 }}</span>
              <el-button link size="small" type="primary" @mousedown.prevent @click.stop.prevent="store.selectCurrentPageAll">本页全选</el-button>
            </div>
          </div>
        </template>
        <el-option v-for="point in store.testPoints" :key="point.id" :label="`${point.module} - ${point.point}`" :value="point.id" :class="{ 'is-checked': store.formData.test_point_ids.includes(point.id) }" @click.stop>
          <div class="tp-item" @mousedown.prevent @click.stop>
            <label class="tp-check" @mousedown.prevent @click.stop>
              <input type="checkbox" :checked="store.formData.test_point_ids.includes(point.id)" @click.stop @change="(e: Event) => { (e.target as HTMLInputElement).checked ? store.addTestPoint(point.id) : store.removeTestPoint(point.id) }" />
            </label>
            <div class="tp-content">
              <div class="tp-row1">
                <span class="tp-mod">{{ point.module }}</span><span class="tp-sep">/</span>
                <span class="tp-point">{{ point.point }}</span>
                <el-tag size="small" :type="store.getPriorityType(point.priority)" round class="tp-pri">{{ store.getPriorityLabel(point.priority) }}</el-tag>
              </div>
              <div class="tp-row2">{{ point.point }}</div>
            </div>
          </div>
        </el-option>
        <template #footer v-if="store.testPointTotal > 0">
          <div class="tp-d-footer" @mousedown.prevent>
            <el-pagination :current-page="store.testPointPage" :page-size="store.testPointPageSize" :total="store.testPointTotal" layout="prev, pager, next, jumper" size="small" @current-change="store.goToTestPointPage" />
          </div>
        </template>
        <template #empty><div class="tp-empty"><p>请先选择需求文档</p></div></template>
      </el-select>
      <transition name="el-fade-in-linear">
        <div class="tp-chips" v-if="store.formData.test_point_ids.length > 0">
          <el-tag v-for="id in store.formData.test_point_ids.slice(0, 6)" :key="id" closable effect="dark" :type="store.getSelectedTagType(id)" size="small" @close="store.removeTestPoint(id)">{{ store.getTestPointLabel(id) }}</el-tag>
          <el-popover v-if="store.formData.test_point_ids.length > 6" placement="bottom-start" :width="280" trigger="hover">
            <template #reference><el-tag effect="dark" type="info" round size="small">+{{ store.formData.test_point_ids.length - 6 }}</el-tag></template>
            <div style="max-height: 200px; overflow-y: auto; padding: 4px 0">
              <el-tag v-for="id in store.formData.test_point_ids.slice(6)" :key="id" closable effect="dark" :type="store.getSelectedTagType(id)" size="small" style="margin: 2px" @close="store.removeTestPoint(id)">{{ store.getTestPointLabel(id) }}</el-tag>
            </div>
          </el-popover>
        </div>
      </transition>
      <div v-if="relatedTestPointIds.length > 0" class="tp-recommend">
        <div class="tp-recommend-header"><el-icon><Connection /></el-icon><span>推荐测试点（基于选中页面路径）</span></div>
        <div class="tp-recommend-list">
          <el-tag v-for="id in relatedTestPointIds" :key="id" :type="store.formData.test_point_ids.includes(id) ? 'success' : 'info'" effect="plain" size="small" class="tp-recommend-tag" @click="store.formData.test_point_ids.includes(id) ? store.removeTestPoint(id) : store.addTestPoint(id)" style="cursor: pointer">
            {{ store.getTestPointLabel(id) }}
            <el-icon v-if="store.formData.test_point_ids.includes(id)" style="margin-left: 2px"><CircleCheck /></el-icon>
          </el-tag>
        </div>
      </div>
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { Search, Connection, CircleCheck } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'

defineProps<{ relatedTestPointIds: number[] }>()
const store = useGenerateStore()
</script>

<style scoped>
.test-point-selector { width: 100%; border-radius: 8px; border: 1px solid #e4e7ed; background: #fff; overflow: hidden; }
.tp-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 14px; background: #f8f9fb; border-bottom: 1px solid #ebeef5; }
.tp-toolbar-left { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #606266; }
.tp-toolbar-left strong { color: #303133; }
.tp-toolbar-right { display: flex; gap: 4px; }
.tp-select { width: 100%; }
.tp-select :deep(.el-input__wrapper) { border-radius: 0; box-shadow: none !important; padding: 4px 12px; background: #fafbfc; }
.tp-select :deep(.el-input__wrapper:hover) { background: #f0f2f5; }
.tp-select :deep(.el-input__wrapper.is-focus) { box-shadow: none !important; background: #fff; }
.tp-chips { padding: 10px 14px; background: #f8f9fb; border-top: 1px solid #ebeef5; display: flex; flex-wrap: wrap; gap: 6px; }
.tp-recommend { padding: 10px 14px; background: #f0f7ff; border-top: 1px solid #d9ecff; }
.tp-recommend-header { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #409eff; margin-bottom: 8px; }
.tp-recommend-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tp-recommend-tag { transition: all 0.2s; }
.tp-recommend-tag:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15); }
</style>
