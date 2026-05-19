<template>
  <el-form-item v-if="store.formData.project_id" label="历史用例">
    <template v-if="store.isLoadingProjectCases">
      <el-skeleton :rows="1" animated />
    </template>
    <template v-else-if="store.projectCases.length > 0">
      <div class="history-case-selector">
        <div class="history-case-toolbar">
          <span class="history-case-stat">共 <strong>{{ store.projectCases.length }}</strong> 条</span>
          <el-tag v-if="store.selectedHistoryCaseIds.length > 0" size="small" type="primary" effect="dark">已选 {{ store.selectedHistoryCaseIds.length }}</el-tag>
          <div class="history-case-actions">
            <el-button link type="primary" size="small" @mousedown.prevent @click.stop.prevent="selectAllHistoryCases" :disabled="store.projectCases.length === 0 || store.selectedHistoryCaseIds.length >= store.projectCases.length">全选</el-button>
            <el-button link type="danger" size="small" @mousedown.prevent @click.stop.prevent="store.selectedHistoryCaseIds = []; store._historyCaseUserCleared = true" :disabled="store.selectedHistoryCaseIds.length === 0">清空</el-button>
          </div>
        </div>
        <el-select v-model="store.selectedHistoryCaseIds" @change="(val: number[]) => { if (val.length > 0) store._historyCaseUserCleared = false; else store._historyCaseUserCleared = true }" multiple filterable clearable collapse-tags collapse-tags-tooltip placeholder="默认评审全部用例，可取消勾选不想评审的用例" style="width: 100%" :max-collapse-tags="3" :loading="store.isLoadingProjectCases">
          <el-option v-for="c in store.projectCases" :key="c.id" :label="`[${c.module}] ${c.title}`" :value="c.id" />
        </el-select>
        <div class="history-case-tip">
          <span v-if="store.selectedHistoryCaseIds.length > 0">已选 {{ store.selectedHistoryCaseIds.length }} 条</span>
          <span v-else>不选择则默认评审项目全部用例</span>
        </div>
      </div>
    </template>
    <template v-else>
      <span style="color: #909399; font-size: 13px">当前项目暂无用例，生成用例后可在此评审查漏补缺</span>
    </template>
  </el-form-item>
</template>

<script setup lang="ts">
import { useGenerateStore } from '@/store/useGenerateStore'

const store = useGenerateStore()
const selectAllHistoryCases = () => { store.selectedHistoryCaseIds = store.projectCases.map((c) => c.id) }
</script>

<style scoped>
.history-case-selector { width: 100%; }
.history-case-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; }
.history-case-stat { color: #606266; }
.history-case-actions { margin-left: auto; display: flex; gap: 4px; }
.history-case-tip { margin-top: 4px; font-size: 12px; color: #909399; }
</style>
