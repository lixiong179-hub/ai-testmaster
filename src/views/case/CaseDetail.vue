<template>
  <div class="case-detail">
    <el-card>
      <template #header>
        <CaseHeader />
      </template>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="10" animated />
      </div>

      <div v-else-if="caseItem" class="case-content">
        <el-alert
          v-if="issueType === 'product_bug'"
          title="这是Bug问题，不要修改用例！"
          description="执行步骤完全正确，但实际结果与预期不符。这可能是产品功能缺陷，请勿修改测试用例来掩盖Bug。"
          type="error"
          show-icon
          :closable="false"
          class="bug-warning-alert"
        />

        <el-alert
          v-if="isCorrectionMode && issueType !== 'product_bug'"
          :title="`纠正模式 - ${failureReason || '用例问题需要纠正'}`"
          description="请检查并修改失败步骤的操作描述、预期结果或定位信息。修改完成后可使用快速验证功能验证。"
          type="warning"
          show-icon
          :closable="true"
          @close="isCorrectionMode = false"
          class="correction-alert"
        />

        <div
          v-if="
            isCorrectionMode && issueType !== 'product_bug' && currentView === VIEW_TYPES.TECHNICAL
          "
          class="quick-verify-bar"
        >
          <el-button type="success" @click="openQuickVerify" :icon="Check"> 快速验证 </el-button>
          <span class="verify-hint">修改完成后，点击快速验证来验证纠正效果</span>
        </div>

        <div class="info-section">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用例编号">
              <span class="case-no">{{ caseItem.case_no }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模块">
              <el-input v-if="isEditing" v-model="editForm.module" placeholder="请输入模块名称" />
              <span v-else>{{ caseItem.module || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="标题">
              <el-input v-if="isEditing" v-model="editForm.title" placeholder="请输入用例标题" />
              <span v-else class="case-title">{{ caseItem.title }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="优先级">
              <el-select v-if="isEditing" v-model="editForm.priority" style="width: 100%">
                <el-option label="高(P1)" :value="1" />
                <el-option label="中(P2)" :value="2" />
                <el-option label="低(P3)" :value="3" />
              </el-select>
              <el-tag v-else :type="getPriorityType(caseItem.priority)">
                {{ getPriorityLabel(caseItem.priority) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="用例类型">
              <el-select v-if="isEditing" v-model="editForm.case_type" style="width: 100%">
                <el-option label="UI自动化" value="ui_automation" />
                <el-option label="手工测试" value="manual" />
                <el-option label="API自动化" value="api_automation" />
                <el-option label="性能测试" value="performance" />
                <el-option label="安全测试" value="security" />
              </el-select>
              <span v-else>{{ getCaseTypeLabel(caseItem.case_type) || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="测试分类">
              <el-select v-if="isEditing" v-model="editForm.test_category" style="width: 100%">
                <el-option label="UI自动化" value="ui_automation" />
                <el-option label="手工测试" value="manual" />
                <el-option label="API自动化" value="api_automation" />
                <el-option label="性能测试" value="performance" />
                <el-option label="安全测试" value="security" />
              </el-select>
              <span v-else>{{ getTestCategoryLabel(caseItem.test_category) || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatTime(caseItem.create_time) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="!isEditing" class="section">
          <div class="section-header">
            <h3 class="section-title">血缘关系</h3>
            <el-button size="small" text @click="lineageExpanded = !lineageExpanded">
              {{ lineageExpanded ? '收起' : '展开' }}
              <el-icon>
                <ArrowUp v-if="lineageExpanded" />
                <ArrowDown v-else />
              </el-icon>
            </el-button>
          </div>
          <div v-show="lineageExpanded">
            <LineageTree :case-id="caseId" />
          </div>
        </div>

        <div class="section">
          <h3 class="section-title">前置条件</h3>
          <div v-if="isEditing" class="editable-content">
            <el-input
              v-model="editForm.precondition"
              type="textarea"
              :rows="3"
              placeholder="请输入前置条件"
            />
          </div>
          <div v-else class="static-content">
            {{ caseItem.precondition || '无' }}
          </div>
        </div>

        <div class="section">
          <div class="section-header">
            <h3 class="section-title">测试步骤</h3>
            <el-button v-if="isEditing" type="primary" size="small" @click="addStep" :icon="Plus">
              添加步骤
            </el-button>
          </div>

          <div v-if="isEditing" class="steps-editor">
            <div
              v-for="(step, index) in editForm.steps"
              :key="step._uid || index"
              class="step-item"
            >
              <div class="step-header">
                <span class="step-number">步骤 {{ index + 1 }}</span>
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  @click="removeStep(index)"
                  :disabled="editForm.steps.length <= 1"
                >
                  删除
                </el-button>
              </div>
              <div class="step-fields">
                <div class="step-field">
                  <label>操作描述</label>
                  <el-input
                    v-model="step.action"
                    type="textarea"
                    :rows="2"
                    placeholder="请输入操作描述"
                  />
                </div>
                <div class="step-field">
                  <label>预期结果</label>
                  <el-input
                    v-model="step.expected_result"
                    type="textarea"
                    :rows="2"
                    placeholder="请输入预期结果"
                  />
                </div>
              </div>
            </div>
            <el-empty v-if="editForm.steps.length === 0" description="暂无步骤，点击上方按钮添加" />
          </div>

          <div v-else-if="currentView === VIEW_TYPES.BUSINESS" class="steps-view">
            <el-table :data="businessSteps" style="width: 100%" border stripe>
              <el-table-column label="步骤" width="80" align="center">
                <template #default="{ $index }">
                  <span class="step-index">{{ $index + 1 }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" min-width="300">
                <template #default="{ row }">
                  <div class="step-content">
                    {{ row.description || row.step || row.action || '-' }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="预期结果" min-width="300">
                <template #default="{ row }">
                  <div class="step-content">{{ row.expected_result || '-' }}</div>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="businessSteps.length === 0" description="暂无测试步骤" />
          </div>

          <CaseTechnicalView v-else-if="currentView === VIEW_TYPES.TECHNICAL" />
        </div>

        <div class="section">
          <h3 class="section-title">总体预期结果</h3>
          <div v-if="isEditing" class="editable-content">
            <el-input
              v-model="editForm.expected_result"
              type="textarea"
              :rows="3"
              placeholder="请输入总体预期结果"
            />
          </div>
          <div v-else class="static-content">
            {{ caseItem.expected_result || '无' }}
          </div>
        </div>

        <div v-if="isEditing" class="save-actions">
          <el-button type="success" size="large" @click="saveEdit" :loading="saving" :icon="Check">
            保存
          </el-button>
          <el-button size="large" @click="cancelEdit" :icon="Close"> 取消 </el-button>
        </div>
      </div>

      <div v-else class="empty-container">
        <el-empty description="未找到测试用例">
          <el-button type="primary" @click="goBack">返回</el-button>
        </el-empty>
      </div>
    </el-card>

    <CaseDialogs />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Check, Plus, Delete, Close, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import LineageTree from '@/components/case/LineageTree.vue'
import { provideCaseDetail, VIEW_TYPES } from '@/composables/case/useCaseDetail'
import CaseHeader from './components/CaseHeader.vue'
import CaseTechnicalView from './components/CaseTechnicalView.vue'
import CaseDialogs from './components/CaseDialogs.vue'

const {
  loading,
  lineageExpanded,
  isCorrectionMode,
  issueType,
  failureReason,
  caseItem,
  isEditing,
  editForm,
  saving,
  currentView,
  businessSteps,
  caseId,
  getPriorityType,
  getPriorityLabel,
  getCaseTypeLabel,
  getTestCategoryLabel,
  formatTime,
  addStep,
  removeStep,
  cancelEdit,
  saveEdit,
  goBack,
  openQuickVerify,
  init,
} = provideCaseDetail()

onMounted(init)
</script>

<style scoped lang="scss">
@use './CaseDetail.scss';
</style>
