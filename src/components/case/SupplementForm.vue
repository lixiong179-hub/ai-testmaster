<template>
  <div class="supplement-form" v-loading="loading">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="推断能力" name="inferred">
        <div v-if="hasInferredCapabilities" class="capability-section">
          <div class="section-toolbar">
            <span class="toolbar-stat">共 {{ inferredCapabilities.length }} 项，已选 {{ selectedInferredCount }} 项</span>
            <div class="toolbar-actions">
              <el-button link type="primary" size="small" @click="selectAllInferred">全选</el-button>
              <el-button link type="danger" size="small" @click="deselectAllInferred">清空</el-button>
            </div>
          </div>
          <div class="capability-list">
            <div v-for="(cap, index) in inferredCapabilities" :key="index" class="capability-item" :class="{ selected: cap.selected }" @click="toggleInferredCapability(index)">
              <el-checkbox :model-value="cap.selected" @change="toggleInferredCapability(index)" @click.stop />
              <div class="capability-content">
                <div class="capability-name">{{ cap.name }}</div>
                <div class="capability-desc">{{ cap.description }}</div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无推断能力" />
      </el-tab-pane>
      <el-tab-pane label="自定义能力" name="custom">
        <div class="custom-capability-section">
          <div v-for="(cap, index) in customCapabilities" :key="index" class="custom-capability-item">
            <el-input v-model="cap.name" placeholder="能力名称" style="width: 200px" />
            <el-input v-model="cap.description" placeholder="能力描述" style="flex: 1; margin-left: 8px" />
            <el-button type="danger" link @click="removeCustomCapability(index)" style="margin-left: 8px"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-button type="primary" plain @click="addCustomCapability" style="margin-top: 8px"><el-icon><Plus /></el-icon>添加自定义能力</el-button>
        </div>
      </el-tab-pane>
      <el-tab-pane label="补充问题" name="questions">
        <div v-if="questions.length > 0" class="questions-section">
          <div v-for="(q, index) in questions" :key="index" class="question-item">
            <div class="question-text">{{ index + 1 }}. {{ q.question }}</div>
            <el-input v-model="q.answer" type="textarea" :rows="2" placeholder="请输入回答" />
          </div>
        </div>
        <el-empty v-else description="暂无补充问题" />
      </el-tab-pane>
    </el-tabs>
    <div v-if="showResult && changeSummary.length > 0" class="change-summary">
      <h4>变更摘要</h4>
      <el-table :data="changeSummary" border size="small">
        <el-table-column prop="field" label="字段" width="120" />
        <el-table-column prop="old_value" label="原值" min-width="150" show-overflow-tooltip />
        <el-table-column prop="new_value" label="新值" min-width="150" show-overflow-tooltip />
      </el-table>
    </div>
    <div class="form-actions">
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSubmit" @click="handleSubmit">提交补充</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { useSupplementForm } from './useSupplementForm'

const props = defineProps<{ caseId: number; projectId: number }>()
const emit = defineEmits<{ cancel: []; saved: [] }>()

const {
  loading, saving, activeTab, inferredCapabilities, customCapabilities,
  questions, showResult, changeSummary, hasInferredCapabilities,
  selectedInferredCount, canSubmit, toggleInferredCapability, selectAllInferred,
  deselectAllInferred, addCustomCapability, removeCustomCapability, handleSubmit,
} = useSupplementForm(props.caseId, props.projectId)
</script>

<style scoped>
.supplement-form { padding: 8px 0; }
.capability-section, .custom-capability-section, .questions-section { display: flex; flex-direction: column; gap: 12px; }
.section-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.toolbar-stat { font-size: 13px; color: #606266; }
.toolbar-actions { display: flex; gap: 4px; }
.capability-list { display: flex; flex-direction: column; gap: 8px; }
.capability-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border: 1px solid #e4e7ed; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
.capability-item:hover { background: #f5f7fa; }
.capability-item.selected { border-color: #409eff; background: #ecf5ff; }
.capability-content { flex: 1; }
.capability-name { font-weight: 600; color: #303133; margin-bottom: 4px; }
.capability-desc { font-size: 13px; color: #606266; line-height: 1.5; }
.custom-capability-item { display: flex; align-items: center; gap: 0; }
.question-item { margin-bottom: 16px; }
.question-text { font-weight: 500; color: #303133; margin-bottom: 8px; }
.change-summary { margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
.change-summary h4 { margin: 0 0 12px; color: #303133; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
</style>
