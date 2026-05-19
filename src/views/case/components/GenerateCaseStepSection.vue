<template>
  <div style="margin-top: 20px">
    <h3>
      测试步骤
      <el-button v-if="store.isEditingResult" type="primary" size="small" @click="store.addEditStep" style="margin-left: 10px">+ 添加步骤</el-button>
    </h3>
    <template v-if="!store.isEditingResult && store.viewingCase">
      <el-timeline>
        <el-timeline-item v-for="(step, index) in store.viewingCase.steps" :key="index" :timestamp="`步骤 ${step.step || Number(index) + 1}`" placement="top">
          <el-card>
            <div class="step-content">
              <div class="step-desc">{{ step.description || step.step }}</div>
              <div class="step-action"><strong>操作:</strong> {{ step.display_action || step.description || step.action }}</div>
              <div v-if="step.test_data && Object.keys(step.test_data).length > 0" class="step-data">
                <strong>测试数据:</strong>
                <el-tag v-for="(value, key) in step.test_data" :key="key" size="small" style="margin: 2px">{{ key }}: {{ value }}</el-tag>
              </div>
              <div class="step-expected"><strong>预期结果:</strong> {{ store.cleanExpectedResult(step.expected_result || '') }}</div>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
      <div v-if="!store.viewingCase.steps || store.viewingCase.steps.length === 0" class="empty-steps">
        <el-empty description="暂无测试步骤" />
      </div>
    </template>
    <template v-else>
      <div class="editable-steps-list">
        <div v-for="(step, index) in store.editingCase.steps" :key="index" class="editable-step-card">
          <div class="step-card-header">
            <span class="step-num">步骤 {{ Number(index) + 1 }}</span>
            <el-button type="danger" size="small" @click="store.removeEditStep(Number(index))" :disabled="store.editingCase.steps.length <= 1">删除</el-button>
          </div>
          <div class="step-card-body">
            <div class="step-edit-field"><label>操作描述：</label><el-input v-model="step.action" placeholder="请输入操作描述" /></div>
            <div class="step-edit-field"><label>预期结果：</label><el-input v-model="step.expected_result" placeholder="请输入预期结果" /></div>
            <div class="step-edit-field"><label>测试数据/参数：</label><el-input v-model="step.param" placeholder="可选" /></div>
          </div>
        </div>
        <div v-if="store.editingCase.steps.length === 0" class="empty-steps-hint"><p>暂无步骤，点击上方"添加步骤"</p></div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useGenerateStore } from '@/store/useGenerateStore'
const store = useGenerateStore()
</script>

<style scoped>
.step-content { line-height: 1.8; }
.step-desc { font-weight: 600; color: #409eff; margin-bottom: 8px; }
.step-action { margin-bottom: 8px; }
.step-data { margin-bottom: 8px; }
.step-expected { color: #67c23a; }
.empty-steps { padding: 40px 0; text-align: center; }
.editable-steps-list .editable-step-card { background: #fafbfc; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.editable-steps-list .step-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.editable-steps-list .step-num { font-weight: 600; color: #409eff; font-size: 14px; }
.editable-steps-list .step-edit-field { margin-bottom: 10px; }
.editable-steps-list .step-edit-field label { display: block; font-size: 12px; color: #606266; margin-bottom: 4px; font-weight: 500; }
.editable-steps-list .empty-steps-hint { text-align: center; padding: 20px; color: #909399; }
</style>
