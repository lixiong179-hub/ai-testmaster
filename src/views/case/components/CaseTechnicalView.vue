<template>
  <div v-if="ctx.viewLoading.value" class="loading-container">
    <el-skeleton :rows="5" animated />
  </div>
  <div v-else-if="ctx.technicalViewData.value">
    <div class="coverage-info">
      <el-alert
        :title="`定位覆盖率: ${ctx.formatLocatorCoverage(ctx.technicalViewData.value.locator_coverage)}`"
        type="info"
        :closable="false"
        show-icon
      />
      <el-button type="primary" size="small" @click="ctx.batchLocatorVisible.value = true" style="margin-left: 12px">
        批量补充定位
      </el-button>
    </div>

    <div v-if="ctx.technicalViewData.value.precondition" class="precondition-section" style="margin-top: 16px">
      <div class="precondition-header" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px">
        <div style="display: flex; align-items: center; gap: 8px">
          <el-icon><Guide /></el-icon>
          <span style="font-weight: 600">前置条件步骤</span>
          <el-tag v-if="ctx.technicalViewData.value.precondition_steps?.length" size="small" type="info">
            {{ ctx.technicalViewData.value.precondition_steps.length }} 个步骤
          </el-tag>
        </div>
        <div style="display: flex; gap: 8px">
          <el-button type="primary" size="small" @click="ctx.parsePrecondition" :loading="ctx.parsePreconditionLoading.value">AI解析</el-button>
          <el-button size="small" @click="ctx.addPreconditionStep">添加步骤</el-button>
        </div>
      </div>
      <el-alert :title="`前置条件: ${ctx.technicalViewData.value.precondition}`" type="info" :closable="false" show-icon style="margin-bottom: 12px" />
      <el-table v-if="ctx.technicalViewData.value.precondition_steps?.length" :data="ctx.technicalViewData.value.precondition_steps" border stripe size="small" style="width: 100%">
        <el-table-column label="步骤" width="60" align="center">
          <template #default="{ row }"><span>{{ row.step_number }}</span></template>
        </el-table-column>
        <el-table-column label="操作" min-width="180">
          <template #default="{ row }"><span>{{ row.action || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="操作类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="ctx.getActionTypeTagType(row.action_type)">{{ row.action_type || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="测试数据" min-width="120">
          <template #default="{ row }">
            <span v-if="row.input_value" style="font-weight: 500">{{ row.input_value }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="目标元素" min-width="120">
          <template #default="{ row }"><span>{{ row.target_element || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="定位状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="ctx.getLocatorStatusType(row.locator_status)" size="small">{{ ctx.getLocatorStatusLabel(row.locator_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="定位类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.locator?.locator_type" size="small" :type="getLocatorTypeTagType(row.locator.locator_type)">{{ getLocatorTypeLabel(row.locator.locator_type) }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="定位值" min-width="200">
          <template #default="{ row }">
            <span v-if="row.locator?.locator_value" style="font-size: 12px; word-break: break-all">{{ row.locator.locator_value }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ $index }">
            <el-button size="small" type="danger" text @click="ctx.deletePreconditionStep($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else style="color: #909399; font-size: 13px; padding: 12px 0">暂无前置条件步骤，点击"AI解析"自动生成，或点击"添加步骤"手动添加</div>
    </div>

    <div v-if="ctx.isCorrectionMode.value && (ctx.failureReason.value || ctx.aiAnalysisText.value)" class="suggestion-panel">
      <div class="suggestion-header">
        <el-icon><Warning /></el-icon>
        <span>智能建议</span>
        <el-button size="small" text @click="ctx.showSuggestionPanel.value = !ctx.showSuggestionPanel.value">
          {{ ctx.showSuggestionPanel.value ? '收起' : '展开' }}
        </el-button>
      </div>
      <div v-if="ctx.showSuggestionPanel.value" class="suggestion-body">
        <div v-if="ctx.failureReason.value" class="suggestion-item"><strong>失败原因：</strong><p>{{ ctx.failureReason.value }}</p></div>
        <div v-if="ctx.aiAnalysisText.value" class="suggestion-item"><strong>AI分析：</strong><p>{{ ctx.aiAnalysisText.value }}</p></div>
      </div>
    </div>

    <el-table :data="ctx.technicalViewData.value.steps" style="width: 100%; margin-top: 16px" border stripe :row-class-name="ctx.getStepRowClass">
      <el-table-column label="步骤" width="80" align="center">
        <template #default="{ row }"><span class="step-index">{{ row.step_number }}</span></template>
      </el-table-column>
      <el-table-column label="操作" min-width="200">
        <template #default="{ row, $index }">
          <div v-if="ctx.editingCell.value?.stepIndex === $index && ctx.editingCell.value?.field === 'action'" class="cell-editing">
            <el-input v-model="ctx.editingValue.value" size="small" />
            <div class="cell-actions">
              <el-button size="small" type="success" @click="ctx.saveCellEdit" :loading="ctx.cellSaving.value">保存</el-button>
              <el-button size="small" @click="ctx.cancelCellEdit">取消</el-button>
            </div>
          </div>
          <div v-else class="cell-display" @dblclick="ctx.startCellEdit($index, 'action', row.action)">
            <span>{{ row.action || '-' }}</span>
            <el-icon v-if="ctx.issueType.value !== 'product_bug'" class="edit-icon"><Edit /></el-icon>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="预期结果" min-width="200">
        <template #default="{ row, $index }">
          <div v-if="ctx.editingCell.value?.stepIndex === $index && ctx.editingCell.value?.field === 'expected_result'" class="cell-editing">
            <el-input v-model="ctx.editingValue.value" size="small" />
            <div class="cell-actions">
              <el-button size="small" type="success" @click="ctx.saveCellEdit" :loading="ctx.cellSaving.value">保存</el-button>
              <el-button size="small" @click="ctx.cancelCellEdit">取消</el-button>
            </div>
          </div>
          <div v-else class="cell-display" @dblclick="ctx.startCellEdit($index, 'expected_result', row.expected_result)">
            <span>{{ row.expected_result || '-' }}</span>
            <el-icon v-if="ctx.issueType.value !== 'product_bug'" class="edit-icon"><Edit /></el-icon>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="定位状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="ctx.getLocatorStatusType(row.locator_status)">{{ ctx.getLocatorStatusLabel(row.locator_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="定位类型" width="110" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.locator?.locator_type" size="small" :type="getLocatorTypeTagType(row.locator.locator_type)">{{ getLocatorTypeLabel(row.locator.locator_type) }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="定位值" min-width="200">
        <template #default="{ row }"><span>{{ row.locator?.locator_value || row.locator?.css_selector || '-' }}</span></template>
      </el-table-column>
      <el-table-column label="XPath" min-width="200">
        <template #default="{ row, $index }">
          <div v-if="ctx.editingCell.value?.stepIndex === $index && ctx.editingCell.value?.field === 'xpath'" class="cell-editing">
            <el-input v-model="ctx.editingValue.value" size="small" />
            <div class="cell-actions">
              <el-button size="small" type="success" @click="ctx.saveCellEdit" :loading="ctx.cellSaving.value">保存</el-button>
              <el-button size="small" @click="ctx.cancelCellEdit">取消</el-button>
            </div>
          </div>
          <div v-else class="cell-display" @dblclick="ctx.startCellEdit($index, 'xpath', row.locator?.xpath)">
            <span>{{ row.locator?.xpath || '-' }}</span>
            <el-icon v-if="ctx.issueType.value !== 'product_bug'" class="edit-icon"><Edit /></el-icon>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="测试数据" min-width="200">
        <template #default="{ row }">
          <div v-if="row.input_value" class="test-data-item">
            <el-tag size="small" type="success" style="margin-right: 4px">{{ row.action_type === 'select' ? '选择' : '输入' }}</el-tag>
            <span class="test-data-value" style="font-weight: 500">{{ row.input_value }}</span>
          </div>
          <div v-else-if="row.test_data && row.test_data.length > 0">
            <div v-for="(td, idx) in row.test_data" :key="idx" class="test-data-item">
              <el-tag size="small" type="info" style="margin-right: 4px">{{ td.field_name }}</el-tag>
              <span class="test-data-value">{{ td.data_value || '-' }}</span>
            </div>
          </div>
          <span v-else class="cell-display">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" v-if="ctx.issueType.value !== 'product_bug'">
        <template #default="{ row, $index }">
          <el-button v-if="!row.locator?.css_selector && !row.locator?.xpath" size="small" type="primary" link @click="ctx.openAddLocator($index, row)">添加定位</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="ctx.technicalViewData.value.steps.length === 0" description="暂无测试步骤" />
  </div>
</template>

<script setup lang="ts">
import { Edit, Warning, Guide } from '@element-plus/icons-vue'
import { useCaseDetail } from '@/composables/case/useCaseDetail'
import { getLocatorTypeLabel, getLocatorTypeTagType } from '@/utils/locatorType'

const ctx = useCaseDetail()
</script>
