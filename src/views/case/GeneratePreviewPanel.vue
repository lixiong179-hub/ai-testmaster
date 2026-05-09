<template>
  <div>
    <!-- 步骤2: 配置测试参数 -->
    <el-card v-if="store.currentStep === 1" class="step-card">
      <template #header>
        <div class="card-header">
          <span>配置测试参数</span>
          <el-button size="small" @click="$emit('prev')">上一步</el-button>
        </div>
      </template>

      <el-form :model="store.formData" label-width="120px">
        <!-- 已选测试点预览 -->
        <el-form-item label="待生成范围">
          <div class="scope-preview">
            <div class="scope-stats">
              <el-statistic title="已选测试点" :value="store.formData.test_point_ids.length" />
              <el-statistic
                title="需求文档"
                :value="store.formData.requirement_file_ids.length"
                class="stat-docs"
              />
              <el-statistic
                title="UI原型"
                :value="store.formData.ui_screen_ids.length || store.formData.ui_file_ids.length"
                class="stat-ui"
              />
            </div>
            <div class="scope-testpoints" v-if="store.selectedTestPointsForDisplay.length > 0">
              <div class="st-list">
                <div v-for="tp in store.selectedTestPointsForDisplay" :key="tp.id" class="st-item">
                  <span class="st-mod">{{ tp.module }}</span>
                  <span class="st-sep">/</span>
                  <span class="st-point">{{ tp.point }}</span>
                  <el-tag size="small" :type="store.getPriorityType(tp.priority)" round>{{
                    store.getPriorityLabel(tp.priority)
                  }}</el-tag>
                </div>
              </div>
              <div class="st-more" v-if="store.formData.test_point_ids.length > 5">
                还有 {{ store.formData.test_point_ids.length - 5 }} 个测试点未展示...
              </div>
            </div>
            <el-alert v-else type="info" :closable="false" show-icon style="margin-top: 8px">
              AI 将基于所选需求文档和测试点自动分析并生成测试用例，无需手动描述场景
            </el-alert>
          </div>
        </el-form-item>

        <!-- 用例类型 -->
        <el-form-item label="用例类型">
          <div class="case-type-group">
            <el-select
              v-model="store.formData.case_type"
              placeholder="请选择用例类型（不选择则由AI智能判断）"
              style="width: 180px"
              @change="store.handleCaseTypeChange"
            >
              <el-option label="UI自动化" value="ui_automation" />
              <el-option label="手工测试" value="manual" />
              <el-option label="API自动化" value="api_automation" />
              <el-option label="性能测试" value="performance" />
              <el-option label="安全测试" value="security" />
            </el-select>

            <!-- UI自动化的执行方式细分 -->
            <div class="exec-mode-group" v-if="store.formData.case_type === 'ui_automation'">
              <span class="exec-label">执行方式：</span>
              <el-radio-group v-model="store.formData.exec_mode" size="small">
                <el-radio-button value="all">
                  全部自动标注
                  <el-tooltip
                    content="AI根据每个用例内容自动判断是UI自动化还是手工测试"
                    placement="top"
                  >
                    <el-icon style="margin-left: 4px; vertical-align: middle; color: #909399"
                      ><InfoFilled
                    /></el-icon>
                  </el-tooltip>
                </el-radio-button>
                <el-radio-button value="ui_auto">仅 UI 自动化</el-radio-button>
                <el-radio-button value="manual">仅手工测试</el-radio-button>
              </el-radio-group>
            </div>

            <!-- API自动化的说明 -->
            <el-alert
              v-if="store.formData.case_type === 'api_automation'"
              type="success"
              :closable="false"
              show-icon
              style="margin-top: 8px; max-width: 500px"
            >
              <template #title>API自动化模式</template>
              AI 将根据接口文档/API定义生成接口级测试用例，包含请求参数、断言规则、响应校验
            </el-alert>

            <!-- 性能测试的说明 -->
            <el-alert
              v-if="store.formData.case_type === 'performance'"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 8px; max-width: 500px"
            >
              <template #title>性能测试模式</template>
              AI 将生成关注响应时间、并发、吞吐量等性能指标的测试用例
            </el-alert>

            <!-- 安全测试的说明 -->
            <el-alert
              v-if="store.formData.case_type === 'security'"
              type="danger"
              :closable="false"
              show-icon
              style="margin-top: 8px; max-width: 500px"
            >
              <template #title>安全测试模式</template>
              AI 将生成涉及XSS、SQL注入、权限绕过等安全验证的测试用例
            </el-alert>
          </div>
        </el-form-item>

        <!-- 补充说明 -->
        <el-form-item label="补充要求">
          <el-input
            v-model="store.formData.extra_requirements"
            type="textarea"
            :rows="3"
            placeholder="可选：补充特殊要求，如&#10;• 需覆盖弱网/断网等异常场景&#10;• 需包含边界值测试&#10;• 兼容 Chrome/Firefox/Safari"
          />
          <div class="form-tip" style="margin-top: 4px">
            不填则由 AI 根据测试点智能判断，通常无需填写
          </div>
        </el-form-item>

        <el-form-item label="优先级">
          <el-select v-model="store.formData.priority" placeholder="请选择优先级">
            <el-option label="P0-高（核心流程）" :value="1" />
            <el-option label="P2-中（主要功能）" :value="2" />
            <el-option label="P3-低（边缘场景）" :value="3" />
          </el-select>
        </el-form-item>

        <el-form-item label="增强模式">
          <el-switch
            v-model="store.formData.enhanced_mode"
            active-text="启用"
            inactive-text="禁用"
          />
          <span class="form-tip">启用后生成含具体测试数据、断言规则的详细用例</span>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            @click="$emit('generate')"
            :loading="store.generating"
            :disabled="store.canGenerate === false"
          >
            <el-icon><MagicStick /></el-icon>
            开始生成 ({{ store.generateButtonLabel }})
          </el-button>
          <el-button @click="store.resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 生成进度 -->
    <el-card v-if="store.generating" class="progress-card">
      <template #header>
        <div class="card-header">
          <span>生成进度</span>
        </div>
      </template>
      <div class="progress-container">
        <el-progress
          :percentage="store.progress"
          :status="store.progressStatus"
          :stroke-width="20"
        />
        <div class="progress-text">{{ store.progressText }}</div>
        <el-button type="danger" @click="store.handleCancel" v-if="store.generating">
          <el-icon><Close /></el-icon>
          取消生成
        </el-button>
      </div>
    </el-card>

    <!-- 生成结果 -->
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
            >
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <template v-else>
              <el-button type="success" size="small" @click="store.handleSaveCase">
                <el-icon><Check /></el-icon>保存
              </el-button>
              <el-button size="small" @click="store.cancelEditResult">取消</el-button>
            </template>
            <el-button
              v-if="!store.isEditingResult"
              type="primary"
              size="small"
              @click="store.handleSaveCase"
              :loading="store.saving"
            >
              <el-icon><Check /></el-icon>保存用例
            </el-button>
          </div>
        </div>
      </template>

      <!-- 用例导航条 -->
      <div class="case-nav-bar" v-if="store.generatedCases.length > 1 && !store.isEditingResult">
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
            }"
            @click="store.currentCaseIndex = idx"
            :title="c.title"
            >{{ idx + 1 }}</span
          >
        </div>
        <button
          class="case-nav-btn"
          :disabled="store.currentCaseIndex >= store.generatedCases.length - 1"
          @click="store.currentCaseIndex++"
        >
          下一条
        </button>
        <div class="case-batch-actions">
          <el-button
            type="success"
            size="small"
            @click="store.saveAllCases"
            :loading="store.saving"
            :disabled="store.generatedCases.every((c) => c._error || c._saved)"
          >
            全部保存 ({{ store.generatedCases.filter((c) => !c._error && !c._saved).length }})
          </el-button>
        </div>
      </div>

      <!-- 错误提示（单条失败） -->
      <el-alert
        v-if="store.viewingCase?._error"
        :title="'生成失败: ' + store.viewingCase._error"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />

      <!-- 查看模式 -->
      <template v-if="!store.isEditingResult && store.viewingCase">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例名称">{{
            store.viewingCase.title
          }}</el-descriptions-item>
          <el-descriptions-item label="关联测试点">
            <el-tag size="small" type="info">{{
              store.viewingCase.test_point_label || '-'
            }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用例类型">
            <el-tag :type="store.getTypeTagType(store.viewingCase.case_type)" size="small">
              {{ store.getTypeLabel(store.viewingCase.case_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="store.getPriorityTagType(store.viewingCase.priority)" size="small">
              {{ store.getPriorityLabel(store.viewingCase.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="评审结果" v-if="store.viewingCase.ai_change_type">
            <el-tag
              :type="store.viewingCase.ai_change_type === 'added' ? 'success' : store.viewingCase.ai_change_type === 'modified' ? 'warning' : 'danger'"
              size="small"
            >
              {{ store.viewingCase.ai_change_type === 'added' ? '查漏·新增' : store.viewingCase.ai_change_type === 'modified' ? '补缺·修正' : '去冗·废弃' }}
            </el-tag>
            <span v-if="store.viewingCase.parent_case_id" style="margin-left: 6px; color: #909399; font-size: 12px">
              源用例 #{{ store.viewingCase.parent_case_id }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="模块">{{
            store.viewingCase.module || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="前置条件" :span="2">{{
            store.viewingCase.precondition || '-'
          }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <!-- 编辑模式 -->
      <template v-else-if="store.isEditingResult">
        <div class="edit-form-grid">
          <div class="edit-field">
            <label>用例名称 *</label>
            <el-input v-model="store.editingCase.title" placeholder="请输入用例名称" />
          </div>
          <div class="edit-field">
            <label>模块</label>
            <el-input v-model="store.editingCase.module" placeholder="请输入模块名称" />
          </div>
          <div class="edit-field">
            <label>用例类型</label>
            <el-select v-model="store.editingCase.case_type" style="width: 100%">
              <el-option label="UI自动化" value="ui_automation" />
              <el-option label="手工测试" value="manual" />
              <el-option label="API自动化" value="api_automation" />
              <el-option label="性能测试" value="performance" />
              <el-option label="安全测试" value="security" />
            </el-select>
          </div>
          <div class="edit-field">
            <label>优先级</label>
            <el-select v-model="store.editingCase.priority" style="width: 100%">
              <el-option label="P0-高" :value="1" />
              <el-option label="P2-中" :value="2" />
              <el-option label="P3-低" :value="3" />
            </el-select>
          </div>
          <div class="edit-field full-width">
            <label>前置条件</label>
            <el-input
              v-model="store.editingCase.precondition"
              type="textarea"
              :rows="3"
              placeholder="请输入前置条件"
            />
          </div>
        </div>
      </template>

      <!-- 测试数据展示 -->
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
              <template #header>
                <span class="test-data-title">{{ store.getDataTypeLabel(key) }}</span>
              </template>
              <div v-for="(value, field) in data" :key="field" class="test-data-item">
                <strong>{{ field }}:</strong> {{ value }}
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- 测试步骤预览/编辑 -->
      <div style="margin-top: 20px">
        <h3>
          测试步骤
          <el-button
            v-if="store.isEditingResult"
            type="primary"
            size="small"
            @click="store.addEditStep"
            style="margin-left: 10px"
            >+ 添加步骤</el-button
          >
        </h3>
        <template v-if="!store.isEditingResult && store.viewingCase">
          <el-timeline>
            <el-timeline-item
              v-for="(step, index) in store.viewingCase.steps"
              :key="index"
              :timestamp="`步骤 ${step.step || Number(index) + 1}`"
              placement="top"
            >
              <el-card>
                <div class="step-content">
                  <div class="step-desc">{{ step.description || step.step }}</div>
                  <div class="step-action"><strong>操作:</strong> {{ step.action }}</div>
                  <div
                    v-if="step.test_data && Object.keys(step.test_data).length > 0"
                    class="step-data"
                  >
                    <strong>测试数据:</strong>
                    <el-tag
                      v-for="(value, key) in step.test_data"
                      :key="key"
                      size="small"
                      style="margin: 2px"
                      >{{ key }}: {{ value }}</el-tag
                    >
                  </div>
                  <div class="step-expected">
                    <strong>预期结果:</strong>
                    {{ store.cleanExpectedResult(step.expected_result || '') }}
                  </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <div
            v-if="!store.viewingCase.steps || store.viewingCase.steps.length === 0"
            class="empty-steps"
          >
            <el-empty description="暂无测试步骤" />
          </div>
        </template>

        <template v-else>
          <div class="editable-steps-list">
            <div
              v-for="(step, index) in store.editingCase.steps"
              :key="index"
              class="editable-step-card"
            >
              <div class="step-card-header">
                <span class="step-num">步骤 {{ Number(index) + 1 }}</span>
                <el-button
                  type="danger"
                  size="small"
                  @click="store.removeEditStep(Number(index))"
                  :disabled="store.editingCase.steps.length <= 1"
                  >删除</el-button
                >
              </div>
              <div class="step-card-body">
                <div class="step-edit-field">
                  <label>操作描述：</label>
                  <el-input v-model="step.action" placeholder="请输入操作描述" />
                </div>
                <div class="step-edit-field">
                  <label>预期结果：</label>
                  <el-input v-model="step.expected_result" placeholder="请输入预期结果" />
                </div>
                <div class="step-edit-field">
                  <label>测试数据/参数：</label>
                  <el-input v-model="step.param" placeholder="可选" />
                </div>
              </div>
            </div>
            <div v-if="store.editingCase.steps.length === 0" class="empty-steps-hint">
              <p>暂无步骤，点击上方"添加步骤"</p>
            </div>
          </div>
        </template>
      </div>

      <!-- 总体预期结果 -->
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
        <el-button @click.stop="store.currentStep = 1">修改配置</el-button>
        <el-button type="primary" @click="store.handleSaveCase" :loading="store.saving"
          >保存当前用例</el-button
        >
        <el-button type="success" @click="store.handleContinueGenerate" :loading="store.generating"
          >基于此用例继续生成</el-button
        >
      </div>
    </el-card>

    <!-- 错误提示 -->
    <el-card v-if="store.errorMessage" class="error-card">
      <template #header>
        <div class="card-header">
          <span>生成失败</span>
        </div>
      </template>
      <div class="error-content">
        <el-alert :title="store.errorMessage" type="error" show-icon :closable="false" />
        <div v-if="store.errorSuggestions.length > 0" class="error-suggestions">
          <h4>优化建议：</h4>
          <ul>
            <li v-for="(suggestion, index) in store.errorSuggestions" :key="index">
              {{ suggestion }}
            </li>
          </ul>
        </div>
        <el-button type="primary" @click="handleRetry" style="margin-top: 15px">
          <el-icon><Refresh /></el-icon>
          重试
        </el-button>
      </div>
    </el-card>
    <FlowIssueDialog
      :visible="store.issueDialogVisible"
      :validation="store.issueDialogValidation"
      @confirm="store.onIssueDialogConfirm"
      @cancel="store.onIssueDialogCancel"
    />
  </div>
</template>

<script setup lang="ts">
import { MagicStick, Close, Check, Refresh, InfoFilled, Edit } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import FlowIssueDialog from '@/components/case/FlowIssueDialog.vue'

const emit = defineEmits<{
  prev: []
  generate: []
}>()

const store = useGenerateStore()

const handleRetry = () => {
  store.handleRetry()
  emit('generate')
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-card,
.progress-card,
.result-card,
.error-card {
  margin-bottom: 20px;
}

/* 待生成范围预览 */
.scope-preview {
  width: 100%;
}

.scope-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #f8f9fb;
  border-radius: 8px;
}

.scope-stats .stat-docs :deep(.el-statistic__head),
.scope-stats .stat-ui :deep(.el-statistic__head) {
  color: #606266;
}

.scope-testpoints {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 14px;
  background: #fafbfc;
  max-height: 240px;
  overflow-y: auto;
}

.st-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.st-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.2s;
}

.st-item:hover {
  background: #ecf5ff;
}

.st-mod {
  color: #409eff;
  font-weight: 600;
  white-space: nowrap;
  min-width: 70px;
}

.st-sep {
  color: #c0c4cc;
}

.st-func {
  color: #303133;
  font-weight: 500;
  white-space: nowrap;
  min-width: 90px;
}

.st-point {
  color: #606266;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

.st-more {
  text-align: center;
  color: #909399;
  font-size: 12px;
  padding: 6px 0;
  border-top: 1px dashed #e4e7ed;
  margin-top: 4px;
}

/* 用例类型分组 */
.case-type-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.exec-mode-group {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding: 10px 14px;
  background: #f8f9fb;
  border-radius: 6px;
}

.exec-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
  font-weight: 500;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

.progress-container {
  text-align: center;
  padding: 20px 0;
}

.progress-text {
  margin: 15px 0;
  font-size: 16px;
  font-weight: 500;
}

.empty-steps {
  padding: 40px 0;
  text-align: center;
}

.error-content {
  padding: 10px 0;
}

.error-suggestions {
  margin-top: 15px;
  padding: 15px;
  background: #fef0f0;
  border-radius: 4px;
}

.error-suggestions h4 {
  margin-top: 0;
  color: #f56c6c;
}

.error-suggestions ul {
  margin: 10px 0 0 0;
  padding-left: 20px;
}

.error-suggestions li {
  margin-bottom: 5px;
  color: #606266;
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

.step-content {
  line-height: 1.8;
}

.step-desc {
  font-weight: 600;
  color: #409eff;
  margin-bottom: 8px;
}

.step-action {
  margin-bottom: 8px;
}

.step-data {
  margin-bottom: 8px;
}

.step-expected {
  color: #67c23a;
}

.expected-result-section {
  margin-top: 20px;
}

.expected-result-section h3 {
  margin-bottom: 10px;
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

/* 用例导航条 */
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

.case-batch-actions {
  margin-left: auto;
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

.editable-steps-list .editable-step-card {
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.editable-steps-list .step-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.editable-steps-list .step-num {
  font-weight: 600;
  color: #409eff;
  font-size: 14px;
}

.editable-steps-list .step-edit-field {
  margin-bottom: 10px;
}

.editable-steps-list .step-edit-field label {
  display: block;
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
  font-weight: 500;
}

.editable-steps-list .empty-steps-hint {
  text-align: center;
  padding: 20px;
  color: #909399;
}
</style>
