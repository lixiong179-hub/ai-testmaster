<template>
  <div class="case-nav-bar" v-if="store.generatedCases.length > 0 && !store.isEditingResult">
    <el-checkbox
      :model-value="store.allSelected"
      @change="store.toggleSelectAll()"
      :indeterminate="store.hasSelected && !store.allSelected"
    />
    <button
      class="case-nav-btn"
      :disabled="store.currentCaseIndex <= 0"
      @click="store.currentCaseIndex--"
    >
      上一条
    </button>
    <div class="case-nav-dots">
      <span
        v-for="(c, idx) in store.generatedCases"
        :key="idx"
        class="case-dot"
        :class="{
          active: idx === store.currentCaseIndex,
          error: c._error,
          saved: c._saved,
          selected: store.selectedCaseIndices.has(idx),
        }"
        @click="store.currentCaseIndex = idx"
        :title="c.title"
      >
        <el-checkbox
          :model-value="store.selectedCaseIndices.has(idx)"
          @change="store.toggleCaseSelection(idx)"
          @click.stop
          size="small"
          class="case-dot-checkbox"
        />
        {{ idx + 1 }}
      </span>
    </div>
    <button
      class="case-nav-btn"
      :disabled="store.currentCaseIndex >= store.generatedCases.length - 1"
      @click="store.currentCaseIndex++"
    >
      下一条
    </button>
    <div class="case-batch-actions" v-if="store.hasSelected">
      <el-button
        type="warning"
        size="small"
        plain
        @click="store.handleRegenerateSelected"
        :loading="store.generating"
      >
        重新生成 ({{ store.selectedCount }})
      </el-button>
      <el-button type="danger" size="small" plain @click="store.handleDeleteSelected">
        删除 ({{ store.selectedCount }})
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useGenerateStore } from '@/store/useGenerateStore'
const store = useGenerateStore()
</script>

<style scoped>
.case-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #f8f9fb;
  border-radius: 6px;
  margin-bottom: 16px;
}
.case-nav-btn {
  padding: 4px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  transition: all 0.2s;
}
.case-nav-btn:hover:not(:disabled) {
  color: #409eff;
  border-color: #409eff;
}
.case-nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.case-nav-dots {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: center;
  max-width: 400px;
}
.case-dot {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #909399;
  transition: all 0.2s;
}
.case-dot:hover {
  border-color: #409eff;
  color: #409eff;
}
.case-dot.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
  font-weight: 600;
}
.case-dot.error {
  background: #fef0f0;
  border-color: #f56c6c;
  color: #f56c6c;
}
.case-dot.saved {
  background: #f0f9eb;
  border-color: #67c23a;
  color: #67c23a;
}
.case-dot.selected {
  box-shadow: 0 0 0 2px #e6a23c;
}
.case-dot-checkbox {
  margin-right: 0;
  height: 14px;
  vertical-align: middle;
}
.case-dot-checkbox :deep(.el-checkbox__inner) {
  width: 12px;
  height: 12px;
}
.case-dot-checkbox :deep(.el-checkbox__inner::after) {
  height: 6px;
  left: 3px;
  top: 1px;
  width: 3px;
}
.case-batch-actions {
  margin-left: auto;
}
</style>
