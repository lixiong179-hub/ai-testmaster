<template>
  <el-card v-if="store.generatedCases.length > 0 && !store.generating" class="result-card">
    <template #header>
      <div class="card-header">
        <span
          >生成结果
          <el-tag size="small" type="info"
            >{{ store.currentCaseIndex + 1 }}/{{ store.generatedCases.length }}</el-tag
          ></span
        >
        <div class="result-actions">
          <el-button
            v-if="!store.isEditingResult"
            type="warning"
            size="small"
            @click="store.startEditResult"
            ><el-icon><Edit /></el-icon>编辑</el-button
          >
          <template v-else>
            <el-button
              type="success"
              size="small"
              @click="store.handleSaveCase"
              :loading="store.saving"
              ><el-icon><Check /></el-icon>保存修改</el-button
            >
            <el-button size="small" @click="store.cancelEditResult">取消</el-button>
          </template>
          <el-button
            v-if="!store.isEditingResult"
            type="danger"
            size="small"
            plain
            @click="store.handleDeleteCase(store.currentCaseIndex)"
            ><el-icon><Delete /></el-icon>删除</el-button
          >
          <el-button
            v-if="!store.isEditingResult"
            type="warning"
            size="small"
            plain
            @click="store.handleRegenerateCase(store.currentCaseIndex)"
            :loading="store.generating"
            ><el-icon><Refresh /></el-icon>重新生成</el-button
          >
        </div>
      </div>
    </template>
    <GenerateCaseNavBar />
    <el-alert
      v-if="store.viewingCase?._error"
      :title="'生成失败: ' + store.viewingCase._error"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    />
    <template v-if="!store.isEditingResult && store.viewingCase">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="用例名称">{{ store.viewingCase.title }}</el-descriptions-item>
        <el-descriptions-item label="关联测试点"
          ><el-tag size="small" type="info">{{
            store.viewingCase.test_point_label || '-'
          }}</el-tag></el-descriptions-item
        >
        <el-descriptions-item label="用例类型"
          ><el-tag :type="store.getTypeTagType(store.viewingCase.case_type)" size="small">{{
            store.getTypeLabel(store.viewingCase.case_type)
          }}</el-tag></el-descriptions-item
        >
        <el-descriptions-item label="优先级"
          ><el-tag :type="store.getPriorityTagType(store.viewingCase.priority)" size="small">{{
            store.getPriorityLabel(store.viewingCase.priority)
          }}</el-tag></el-descriptions-item
        >
        <el-descriptions-item label="评审结果" v-if="store.viewingCase.ai_change_type">
          <el-tag
            :type="
              store.viewingCase.ai_change_type === 'added'
                ? 'success'
                : store.viewingCase.ai_change_type === 'modified'
                  ? 'warning'
                  : 'danger'
            "
            size="small"
          >
            {{
              store.viewingCase.ai_change_type === 'added'
                ? '查漏·新增'
                : store.viewingCase.ai_change_type === 'modified'
                  ? '补缺·修正'
                  : '去冗·废弃'
            }}
          </el-tag>
          <span
            v-if="store.viewingCase.parent_case_id"
            style="margin-left: 6px; color: #909399; font-size: 12px"
            >源用例 #{{ store.viewingCase.parent_case_id }}</span
          >
        </el-descriptions-item>
        <el-descriptions-item label="模块">{{
          store.viewingCase.module || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="前置条件" :span="2">{{
          store.viewingCase.precondition || '-'
        }}</el-descriptions-item>
      </el-descriptions>
    </template>
    <template v-else-if="store.isEditingResult">
      <div class="edit-form-grid">
        <div class="edit-field">
          <label>用例名称 *</label
          ><el-input v-model="store.editingCase.title" placeholder="请输入用例名称" />
        </div>
        <div class="edit-field">
          <label>模块</label
          ><el-input v-model="store.editingCase.module" placeholder="请输入模块名称" />
        </div>
        <div class="edit-field">
          <label>用例类型</label>
          <el-select v-model="store.editingCase.case_type" style="width: 100%">
            <el-option label="UI自动化" value="ui_automation" /><el-option
              label="手工测试"
              value="manual"
            />
            <el-option label="API自动化" value="api_automation" /><el-option
              label="性能测试"
              value="performance"
            />
            <el-option label="安全测试" value="security" />
          </el-select>
        </div>
        <div class="edit-field">
          <label>优先级</label>
          <el-select v-model="store.editingCase.priority" style="width: 100%">
            <el-option label="P0-高" :value="1" /><el-option label="P2-中" :value="2" /><el-option
              label="P3-低"
              :value="3"
            />
          </el-select>
        </div>
        <div class="edit-field full-width">
          <label>前置条件</label
          ><el-input
            v-model="store.editingCase.precondition"
            type="textarea"
            :rows="3"
            placeholder="请输入前置条件"
          />
        </div>
      </div>
    </template>
    <div
      v-if="
        store.viewingCase?.test_data &&
        Object.keys(store.viewingCase.test_data).length > 0 &&
        !store.isEditingResult
      "
      class="test-data-section"
    >
      <h3>测试数据</h3>
      <el-row :gutter="20">
        <el-col :span="8" v-for="(data, key) in store.viewingCase.test_data" :key="key">
          <el-card shadow="hover" class="test-data-card">
            <template #header
              ><span class="test-data-title">{{ store.getDataTypeLabel(key) }}</span></template
            >
            <div v-for="(value, field) in data" :key="field" class="test-data-item">
              <strong>{{ field }}:</strong> {{ value }}
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
    <GenerateCaseStepSection />
    <div
      v-if="store.viewingCase?.expected_result && !store.isEditingResult"
      class="expected-result-section"
    >
      <h3>总体预期结果</h3>
      <el-alert
        :title="store.cleanExpectedResult(store.viewingCase.expected_result)"
        type="success"
        :closable="false"
        show-icon
      />
    </div>
    <div v-else-if="store.isEditingResult" class="expected-result-section">
      <h3>总体预期结果</h3>
      <el-input
        v-model="store.editingCase.expected_result"
        type="textarea"
        :rows="2"
        placeholder="请输入总体预期结果"
      />
    </div>
    <div class="result-actions-bottom" v-if="!store.isEditingResult">
      <el-button type="info" @click.stop="store.currentStep = 1">调整配置重新生成</el-button>
      <el-button type="primary" @click="$emit('finish')">完成</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Check, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import GenerateCaseNavBar from './GenerateCaseNavBar.vue'
import GenerateCaseStepSection from './GenerateCaseStepSection.vue'

defineEmits<{ finish: [] }>()
const store = useGenerateStore()
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-card {
  margin-bottom: 20px;
}
.result-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.result-actions-bottom {
  margin-top: 30px;
  text-align: center;
  padding-top: 20px;
  border-top: 1px solid #eee;
}
.edit-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.edit-form-grid .edit-field label {
  display: block;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  font-weight: 500;
}
.edit-form-grid .edit-field.full-width {
  grid-column: 1 / -1;
}
.test-data-section {
  margin-top: 20px;
}
.test-data-section h3 {
  margin-bottom: 15px;
}
.test-data-card {
  margin-bottom: 10px;
}
.test-data-title {
  font-weight: 600;
}
.test-data-item {
  margin-bottom: 5px;
  font-size: 14px;
}
.expected-result-section {
  margin-top: 20px;
}
.expected-result-section h3 {
  margin-bottom: 10px;
}
</style>
