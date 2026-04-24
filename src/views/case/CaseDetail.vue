<template>
  <div class="case-detail">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <el-button type="info" @click="goBack" :icon="ArrowLeft"> 返回 </el-button>
            <h2>测试用例详情</h2>
            <el-tag v-if="caseItem" type="info">
              {{ caseItem.case_no }}
            </el-tag>
            <el-tag v-if="isCorrectionMode" type="warning" effect="dark"> 纠正模式 </el-tag>
          </div>
          <div class="header-right">
            <el-radio-group
              v-if="!isEditing"
              v-model="currentView"
              size="small"
              @change="handleViewChange"
            >
              <el-radio-button :value="VIEW_TYPES.BUSINESS">业务视图</el-radio-button>
              <el-radio-button :value="VIEW_TYPES.TECHNICAL">技术视图</el-radio-button>
            </el-radio-group>
            <el-button
              type="success"
              @click="copyCase"
              :icon="DocumentCopy"
              :disabled="issueType === 'product_bug'"
            >
              复制用例
            </el-button>
            <el-button @click="openVersionHistory" :disabled="!caseId"> 版本历史 </el-button>
            <el-button
              v-if="issueType !== 'product_bug'"
              type="primary"
              @click="toggleEdit"
              :icon="isEditing ? Close : Edit"
            >
              {{ isEditing ? '取消' : '编辑' }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="10" animated />
      </div>

      <!-- 用例内容 -->
      <div v-else-if="caseItem" class="case-content">
        <!-- Bug问题警告 -->
        <el-alert
          v-if="issueType === 'product_bug'"
          title="这是Bug问题，不要修改用例！"
          description="执行步骤完全正确，但实际结果与预期不符。这可能是产品功能缺陷，请勿修改测试用例来掩盖Bug。"
          type="error"
          show-icon
          :closable="false"
          class="bug-warning-alert"
        />

        <!-- 纠正模式提示 -->
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

        <!-- 快速验证按钮 -->
        <div
          v-if="
            isCorrectionMode && issueType !== 'product_bug' && currentView === VIEW_TYPES.TECHNICAL
          "
          class="quick-verify-bar"
        >
          <el-button type="success" @click="openQuickVerify" :icon="Check"> 快速验证 </el-button>
          <span class="verify-hint">修改完成后，点击快速验证来验证纠正效果</span>
        </div>

        <!-- 基本信息 -->
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

        <!-- 前置条件 -->
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

        <!-- 测试步骤 -->
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

          <!-- 业务视图 -->
          <div v-else-if="currentView === VIEW_TYPES.BUSINESS" class="steps-view">
            <el-table :data="businessSteps" style="width: 100%" border stripe>
              <el-table-column label="步骤" width="80" align="center">
                <template #default="{ $index }">
                  <span class="step-index">{{ $index + 1 }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" min-width="300">
                <template #default="{ row }">
                  <div class="step-content">{{ row.action || '-' }}</div>
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

          <!-- 技术视图 -->
          <div v-else-if="currentView === VIEW_TYPES.TECHNICAL" class="steps-view">
            <div v-if="viewLoading" class="loading-container">
              <el-skeleton :rows="5" animated />
            </div>
            <div v-else-if="technicalViewData">
              <!-- 定位覆盖率 -->
              <div class="coverage-info">
                <el-alert
                  :title="`定位覆盖率: ${technicalViewData ? formatLocatorCoverage(technicalViewData.locator_coverage) : '0%'}`"
                  type="info"
                  :closable="false"
                  show-icon
                />
                <el-button
                  type="primary"
                  size="small"
                  @click="batchLocatorVisible = true"
                  style="margin-left: 12px"
                >
                  批量补充定位
                </el-button>
              </div>

              <!-- 前置条件步骤 -->
              <div
                v-if="technicalViewData.precondition"
                class="precondition-section"
                style="margin-top: 16px"
              >
                <div
                  class="precondition-header"
                  style="
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 12px;
                  "
                >
                  <div style="display: flex; align-items: center; gap: 8px">
                    <el-icon><Guide /></el-icon>
                    <span style="font-weight: 600">前置条件步骤</span>
                    <el-tag
                      v-if="technicalViewData.precondition_steps?.length"
                      size="small"
                      type="info"
                    >
                      {{ technicalViewData.precondition_steps.length }} 个步骤
                    </el-tag>
                  </div>
                  <div style="display: flex; gap: 8px">
                    <el-button
                      type="primary"
                      size="small"
                      @click="parsePrecondition"
                      :loading="parsePreconditionLoading"
                    >
                      AI解析
                    </el-button>
                    <el-button size="small" @click="addPreconditionStep"> 添加步骤 </el-button>
                  </div>
                </div>

                <!-- 前置条件文本 -->
                <el-alert
                  :title="`前置条件: ${technicalViewData.precondition}`"
                  type="info"
                  :closable="false"
                  show-icon
                  style="margin-bottom: 12px"
                />

                <!-- 前置条件步骤表格 -->
                <el-table
                  v-if="technicalViewData.precondition_steps?.length"
                  :data="technicalViewData.precondition_steps"
                  border
                  stripe
                  size="small"
                  style="width: 100%"
                >
                  <el-table-column label="步骤" width="60" align="center">
                    <template #default="{ row }">
                      <span>{{ row.step_number }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" min-width="180">
                    <template #default="{ row }">
                      <span>{{ row.action || '-' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作类型" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag size="small" :type="getActionTypeTagType(row.action_type)">{{
                        row.action_type || '-'
                      }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="测试数据" min-width="120">
                    <template #default="{ row }">
                      <span v-if="row.input_value" style="font-weight: 500">{{
                        row.input_value
                      }}</span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="目标元素" min-width="120">
                    <template #default="{ row }">
                      <span>{{ row.target_element || '-' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="定位状态" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag :type="getLocatorStatusType(row.locator_status)" size="small">
                        {{ getLocatorStatusLabel(row.locator_status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="定位类型" width="110" align="center">
                    <template #default="{ row }">
                      <el-tag
                        v-if="row.locator?.locator_type"
                        size="small"
                        :type="getLocatorTypeTagType(row.locator.locator_type)"
                      >
                        {{ getLocatorTypeLabel(row.locator.locator_type) }}
                      </el-tag>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="定位值" min-width="200">
                    <template #default="{ row }">
                      <span
                        v-if="row.locator?.locator_value"
                        style="font-size: 12px; word-break: break-all"
                      >
                        {{ row.locator.locator_value }}
                      </span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="120" align="center">
                    <template #default="{ $index }">
                      <el-button
                        size="small"
                        type="danger"
                        text
                        @click="deletePreconditionStep($index)"
                        >删除</el-button
                      >
                    </template>
                  </el-table-column>
                </el-table>

                <div v-else style="color: #909399; font-size: 13px; padding: 12px 0">
                  暂无前置条件步骤，点击"AI解析"自动生成，或点击"添加步骤"手动添加
                </div>
              </div>

              <!-- 智能建议面板 -->
              <div
                v-if="isCorrectionMode && (failureReason || aiAnalysisText)"
                class="suggestion-panel"
              >
                <div class="suggestion-header">
                  <el-icon><Warning /></el-icon>
                  <span>智能建议</span>
                  <el-button size="small" text @click="showSuggestionPanel = !showSuggestionPanel">
                    {{ showSuggestionPanel ? '收起' : '展开' }}
                  </el-button>
                </div>
                <div v-if="showSuggestionPanel" class="suggestion-body">
                  <div v-if="failureReason" class="suggestion-item">
                    <strong>失败原因：</strong>
                    <p>{{ failureReason }}</p>
                  </div>
                  <div v-if="aiAnalysisText" class="suggestion-item">
                    <strong>AI分析：</strong>
                    <p>{{ aiAnalysisText }}</p>
                  </div>
                </div>
              </div>

              <el-table
                :data="technicalViewData.steps"
                style="width: 100%; margin-top: 16px"
                border
                stripe
                :row-class-name="getStepRowClass"
              >
                <el-table-column label="步骤" width="80" align="center">
                  <template #default="{ row }">
                    <span class="step-index">{{ row.step_number }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" min-width="200">
                  <template #default="{ row, $index }">
                    <div
                      v-if="editingCell?.stepIndex === $index && editingCell?.field === 'action'"
                      class="cell-editing"
                    >
                      <el-input v-model="editingValue" size="small" />
                      <div class="cell-actions">
                        <el-button
                          size="small"
                          type="success"
                          @click="saveCellEdit"
                          :loading="cellSaving"
                          >保存</el-button
                        >
                        <el-button size="small" @click="cancelCellEdit">取消</el-button>
                      </div>
                    </div>
                    <div
                      v-else
                      class="cell-display"
                      @dblclick="startCellEdit($index, 'action', row.action)"
                    >
                      <span>{{ row.action || '-' }}</span>
                      <el-icon v-if="issueType !== 'product_bug'" class="edit-icon"
                        ><Edit
                      /></el-icon>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="预期结果" min-width="200">
                  <template #default="{ row, $index }">
                    <div
                      v-if="
                        editingCell?.stepIndex === $index &&
                        editingCell?.field === 'expected_result'
                      "
                      class="cell-editing"
                    >
                      <el-input v-model="editingValue" size="small" />
                      <div class="cell-actions">
                        <el-button
                          size="small"
                          type="success"
                          @click="saveCellEdit"
                          :loading="cellSaving"
                          >保存</el-button
                        >
                        <el-button size="small" @click="cancelCellEdit">取消</el-button>
                      </div>
                    </div>
                    <div
                      v-else
                      class="cell-display"
                      @dblclick="startCellEdit($index, 'expected_result', row.expected_result)"
                    >
                      <span>{{ row.expected_result || '-' }}</span>
                      <el-icon v-if="issueType !== 'product_bug'" class="edit-icon"
                        ><Edit
                      /></el-icon>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="定位状态" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getLocatorStatusType(row.locator_status)">
                      {{ getLocatorStatusLabel(row.locator_status) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="定位类型" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag
                      v-if="row.locator?.locator_type"
                      size="small"
                      :type="getLocatorTypeTagType(row.locator.locator_type)"
                    >
                      {{ getLocatorTypeLabel(row.locator.locator_type) }}
                    </el-tag>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="定位值" min-width="200">
                  <template #default="{ row }">
                    <span>{{
                      row.locator?.locator_value || row.locator?.css_selector || '-'
                    }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="XPath" min-width="200">
                  <template #default="{ row, $index }">
                    <div
                      v-if="editingCell?.stepIndex === $index && editingCell?.field === 'xpath'"
                      class="cell-editing"
                    >
                      <el-input v-model="editingValue" size="small" />
                      <div class="cell-actions">
                        <el-button
                          size="small"
                          type="success"
                          @click="saveCellEdit"
                          :loading="cellSaving"
                          >保存</el-button
                        >
                        <el-button size="small" @click="cancelCellEdit">取消</el-button>
                      </div>
                    </div>
                    <div
                      v-else
                      class="cell-display"
                      @dblclick="startCellEdit($index, 'xpath', row.locator?.xpath)"
                    >
                      <span>{{ row.locator?.xpath || '-' }}</span>
                      <el-icon v-if="issueType !== 'product_bug'" class="edit-icon"
                        ><Edit
                      /></el-icon>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="测试数据" min-width="200">
                  <template #default="{ row }">
                    <div v-if="row.input_value" class="test-data-item">
                      <el-tag size="small" type="success" style="margin-right: 4px">{{
                        row.action_type === 'select' ? '选择' : '输入'
                      }}</el-tag>
                      <span class="test-data-value" style="font-weight: 500">{{
                        row.input_value
                      }}</span>
                    </div>
                    <div v-else-if="row.test_data && row.test_data.length > 0">
                      <div v-for="(td, idx) in row.test_data" :key="idx" class="test-data-item">
                        <el-tag size="small" type="info" style="margin-right: 4px">{{
                          td.field_name
                        }}</el-tag>
                        <span class="test-data-value">{{ td.data_value || '-' }}</span>
                      </div>
                    </div>
                    <span v-else class="cell-display">-</span>
                  </template>
                </el-table-column>
                <el-table-column
                  label="操作"
                  width="100"
                  align="center"
                  v-if="issueType !== 'product_bug'"
                >
                  <template #default="{ row, $index }">
                    <el-button
                      v-if="!row.locator?.css_selector && !row.locator?.xpath"
                      size="small"
                      type="primary"
                      link
                      @click="openAddLocator($index, row)"
                    >
                      添加定位
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="technicalViewData.steps.length === 0" description="暂无测试步骤" />
            </div>
          </div>
        </div>

        <!-- 总体预期结果 -->
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

        <!-- 保存按钮 -->
        <div v-if="isEditing" class="save-actions">
          <el-button type="success" size="large" @click="saveEdit" :loading="saving" :icon="Check">
            保存
          </el-button>
          <el-button size="large" @click="cancelEdit" :icon="Close"> 取消 </el-button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-container">
        <el-empty description="未找到测试用例">
          <el-button type="primary" @click="goBack">返回</el-button>
        </el-empty>
      </div>
    </el-card>

    <!-- 快速验证对话框 -->
    <el-dialog v-model="quickVerifyVisible" title="快速验证" width="500px">
      <p>选择要验证的步骤：</p>
      <el-checkbox-group v-model="selectedVerifySteps">
        <div v-if="technicalViewData" class="verify-step-list">
          <el-checkbox
            v-for="step in technicalViewData.steps"
            :key="step.step_number"
            :value="step.step_number"
            :label="step.step_number"
          >
            步骤 {{ step.step_number }}: {{ step.action?.substring(0, 50) || '-'
            }}{{ step.action?.length > 50 ? '...' : '' }}
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="quickVerifyVisible = false">取消</el-button>
        <el-button type="primary" @click="executeQuickVerify" :loading="quickVerifyLoading">
          开始验证
        </el-button>
      </template>
    </el-dialog>

    <!-- 版本历史对话框 -->
    <el-dialog v-model="versionHistoryVisible" title="版本历史" width="700px">
      <div v-if="versionLoading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>
      <div v-else>
        <el-table :data="versionList" style="width: 100%" border stripe>
          <el-table-column label="版本号" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small">v{{ row.version_number }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="修改类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                :type="
                  row.change_type === 'correction'
                    ? 'warning'
                    : row.change_type === 'rollback'
                      ? 'info'
                      : ''
                "
                size="small"
              >
                {{
                  row.change_type === 'correction'
                    ? '纠正'
                    : row.change_type === 'update'
                      ? '编辑'
                      : row.change_type === 'rollback'
                        ? '回滚'
                        : row.change_type === 'create'
                          ? '创建'
                          : row.change_type
                }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="修改说明" min-width="200">
            <template #default="{ row }">
              {{ row.change_description || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作人" width="100">
            <template #default="{ row }">
              {{ row.operator_name || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="修改时间" width="160">
            <template #default="{ row }">
              {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-popconfirm
                title="确定要回滚到此版本吗？当前数据将被覆盖。"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleRollback(row)"
              >
                <template #reference>
                  <el-button size="small" type="warning" :loading="rollbackLoading">
                    回滚
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <div class="version-pagination">
          <el-pagination
            v-model:current-page="versionPage"
            :page-size="20"
            :total="versionTotal"
            layout="total, prev, pager, next"
            @current-change="fetchVersionHistory"
          />
        </div>
      </div>
    </el-dialog>

    <!-- 添加定位对话框 -->
    <el-dialog v-model="addLocatorVisible" title="添加元素定位" width="500px">
      <el-form :model="addLocatorForm" label-width="100px">
        <el-form-item label="CSS选择器">
          <el-input
            v-model="addLocatorForm.css_selector"
            placeholder="例如: #username, .login-btn"
          />
        </el-form-item>
        <el-form-item label="XPath">
          <el-input v-model="addLocatorForm.xpath" placeholder="例如: //input[@name='username']" />
        </el-form-item>
        <el-form-item label="AI坐标">
          <el-input v-model="addLocatorForm.ai_coordinate" placeholder="例如: 100,200" />
        </el-form-item>
        <el-form-item label="定位方式">
          <el-radio-group v-model="addLocatorForm.locator_type">
            <el-radio value="css">CSS选择器</el-radio>
            <el-radio value="xpath">XPath</el-radio>
            <el-radio value="ai">AI坐标</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addLocatorVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAddLocator" :loading="addLocatorLoading">
          保存
        </el-button>
      </template>
    </el-dialog>

    <BatchLocatorDialog
      v-model="batchLocatorVisible"
      :case-id="caseId"
      @success="fetchTechnicalView"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Close,
  Check,
  Plus,
  Delete,
  DocumentCopy,
  Warning,
  Guide,
} from '@element-plus/icons-vue'
import { testCaseApi } from '@/api/case'
import { testCaseViewApi } from '@/api/testCaseView'
import { createQuickVerify } from '@/api/testExecution'
import type { TestCase } from '@/types/testCase'
import type { TechnicalView } from '@/api/testCaseView'
import BatchLocatorDialog from './BatchLocatorDialog.vue'
import { getLocatorTypeLabel, getLocatorTypeTagType } from '@/utils/locatorType'

// ==================== 常量定义 ====================
const PRIORITY_MAP: Record<number, { label: string; type: any }> = {
  1: { label: '高(P1)', type: 'danger' },
  2: { label: '中(P2)', type: 'warning' },
  3: { label: '低(P3)', type: 'success' },
}

const DEFAULT_PRIORITY = 2

const LOCATOR_STATUS_MAP: Record<string, { label: string; type: string }> = {
  recorded: { label: '已定位', type: 'success' },
  pending: { label: '待定位', type: 'warning' },
  failed: { label: '定位失败', type: 'danger' },
}

const VIEW_TYPES = {
  BUSINESS: 'business',
  TECHNICAL: 'technical',
} as const

const route = useRoute()
const router = useRouter()

// 状态
const loading = ref(false)
const saving = ref(false)
const isEditing = ref(false)
const currentView = ref<(typeof VIEW_TYPES)[keyof typeof VIEW_TYPES]>(VIEW_TYPES.BUSINESS)
const viewLoading = ref(false)
const technicalViewData = ref<TechnicalView | null>(null)

// 纠正模式相关状态
const isCorrectionMode = ref(false)
const correctionStepIndex = ref(-1)
const issueType = ref<'case_issue' | 'product_bug' | 'needs_review'>('case_issue')
const failureReason = ref('')
const aiAnalysisText = ref('')

// 技术视图内联编辑状态
const editingCell = ref<{ stepIndex: number; field: string } | null>(null)
const editingValue = ref('')
const cellSaving = ref(false)
const showSuggestionPanel = ref(true)

// 快速验证相关状态
const quickVerifyVisible = ref(false)
const quickVerifyLoading = ref(false)
const selectedVerifySteps = ref<number[]>([])

// 版本历史相关状态
const versionHistoryVisible = ref(false)
const versionList = ref<any[]>([])
const versionLoading = ref(false)
const versionTotal = ref(0)
const versionPage = ref(1)
const rollbackLoading = ref(false)

// 快速添加定位相关状态
const addLocatorVisible = ref(false)
const addLocatorLoading = ref(false)
const addLocatorStepIndex = ref(-1)
const batchLocatorVisible = ref(false)
const addLocatorForm = ref({
  css_selector: '',
  xpath: '',
  ai_coordinate: '',
  locator_type: 'css',
})

// 前置条件步骤相关状态
const parsePreconditionLoading = ref(false)

// 用例数据
const caseItem = ref<TestCase | null>(null)

// 编辑表单
const editForm = ref({
  title: '',
  module: '',
  precondition: '',
  expected_result: '',
  priority: DEFAULT_PRIORITY,
  case_type: '',
  test_category: '',
  steps: [] as Array<{
    _uid?: number
    step_number?: number
    action: string
    expected_result: string
    param?: string
  }>,
})

// 计算属性 - 业务视图步骤
const businessSteps = computed(() => {
  if (!caseItem.value?.steps) return []
  return caseItem.value.steps
})

// 获取用例ID
const caseId = computed(() => Number(route.params.caseId) || 0)

// ==================== 工具函数 ====================
const getPriorityType = (priority: number) => {
  return PRIORITY_MAP[priority]?.type || 'info'
}

const getPriorityLabel = (priority: number) => {
  return PRIORITY_MAP[priority]?.label || '中(P2)'
}

const getCaseTypeLabel = (type?: string) => {
  const typeMap: Record<string, string> = {
    ui_automation: 'UI自动化',
    manual: '手工测试',
    api_automation: 'API自动化',
    performance: '性能测试',
    security: '安全测试',
    UI: 'UI自动化',
    API: 'API自动化',
    功能: '手工测试',
    功能测试: '手工测试',
    functional: '手工测试',
  }
  return typeMap[type || ''] || type || '-'
}

const getTestCategoryLabel = (category?: string) => {
  return getCaseTypeLabel(category)
}

const formatTime = (time?: string) => {
  if (!time) return '-'
  try {
    return new Date(time).toLocaleString('zh-CN')
  } catch {
    return time
  }
}

// 获取用例详情
const fetchCaseDetail = async () => {
  if (!caseId.value) return

  loading.value = true
  try {
    caseItem.value = (await testCaseApi.getCase(caseId.value)) as TestCase

    if (caseItem.value && !caseItem.value.steps) {
      caseItem.value.steps = []
    }

    // 初始化编辑表单
    initEditForm()
  } catch (error: any) {
    console.error('获取用例详情失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '获取用例详情失败'
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

// 初始化编辑表单
const initEditForm = () => {
  if (!caseItem.value) return

  editForm.value = {
    title: caseItem.value.title || '',
    module: caseItem.value.module || '',
    precondition: caseItem.value.precondition || '',
    expected_result: caseItem.value.expected_result || '',
    priority: caseItem.value.priority || 2,
    case_type: caseItem.value.case_type || '',
    test_category: caseItem.value.test_category || '',
    steps: caseItem.value.steps ? JSON.parse(JSON.stringify(caseItem.value.steps)) : [],
  }
}

// 切换编辑状态
const toggleEdit = () => {
  if (isEditing.value) {
    cancelEdit()
  } else {
    isEditing.value = true
    initEditForm()
  }
}

// 取消编辑
const cancelEdit = () => {
  isEditing.value = false
  initEditForm()
}

// 保存编辑
const saveEdit = async () => {
  // 验证
  if (!editForm.value.title.trim()) {
    ElMessage.warning('请输入用例标题')
    return
  }
  if (editForm.value.steps.length === 0) {
    ElMessage.warning('请至少添加一个测试步骤')
    return
  }

  saving.value = true
  try {
    // 构建更新数据
    const updateData: any = {
      title: editForm.value.title,
      module: editForm.value.module,
      precondition: editForm.value.precondition,
      expected_result: editForm.value.expected_result,
      priority: editForm.value.priority,
      case_type: editForm.value.case_type,
      test_category: editForm.value.test_category,
      steps: editForm.value.steps,
    }

    await testCaseApi.updateCase(caseId.value, updateData)
    ElMessage.success('保存成功')
    isEditing.value = false

    // 重新获取数据
    await fetchCaseDetail()
  } catch (error: any) {
    console.error('保存失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '保存失败'
    ElMessage.error(errorMsg)
  } finally {
    saving.value = false
  }
}

// 添加步骤
const addStep = () => {
  editForm.value.steps.push({
    _uid: Date.now() + Math.random(),
    action: '',
    expected_result: '',
  })
}

// 删除步骤
const removeStep = (index: number) => {
  if (editForm.value.steps.length > 1) {
    editForm.value.steps.splice(index, 1)
  }
}

// 复制用例
const copyCase = async () => {
  if (!caseItem.value) return

  const caseText =
    `用例编号: ${caseItem.value.case_no}\n` +
    `模块: ${caseItem.value.module || '-'}\n` +
    `标题: ${caseItem.value.title}\n` +
    `前置条件: ${caseItem.value.precondition || '-'}\n` +
    `测试步骤:\n${(caseItem.value.steps || []).map((step, i) => `${i + 1}. ${step.action || '-'}\n   预期结果: ${step.expected_result || '-'}`).join('\n')}\n` +
    `总体预期结果: ${caseItem.value.expected_result || '-'}\n` +
    `优先级: ${getPriorityLabel(caseItem.value.priority)}\n` +
    `用例类型: ${caseItem.value.case_type || '-'}`

  try {
    // 优先使用现代 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(caseText)
      ElMessage.success('用例已复制到剪贴板')
    } else {
      // 降级方案：使用传统的 textarea 方法
      const textArea = document.createElement('textarea')
      textArea.value = caseText
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      textArea.style.top = '-999999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()

      try {
        const successful = document.execCommand('copy')
        if (successful) {
          ElMessage.success('用例已复制到剪贴板')
        } else {
          ElMessage.error('复制失败，请手动复制')
        }
      } catch (err) {
        console.error('复制失败:', err)
        ElMessage.error('复制失败，请手动复制')
      } finally {
        document.body.removeChild(textArea)
      }
    }
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败，请手动复制')
  }
}

// 获取技术视图
const fetchTechnicalView = async () => {
  if (!caseId.value) return
  viewLoading.value = true
  try {
    technicalViewData.value = await testCaseViewApi.getTechnicalView(caseId.value)
  } catch (error: any) {
    console.error('获取技术视图失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '获取技术视图失败'
    ElMessage.error(errorMsg)
  } finally {
    viewLoading.value = false
  }
}

// 切换视图
const handleViewChange = async (view: (typeof VIEW_TYPES)[keyof typeof VIEW_TYPES]) => {
  if (currentView.value === view) return
  currentView.value = view
  if (view === VIEW_TYPES.TECHNICAL) {
    await fetchTechnicalView()
  }
}

// 获取定位状态标签类型
const getLocatorStatusType = (status: string) => {
  return LOCATOR_STATUS_MAP[status]?.type || 'info'
}

// 获取定位状态标签文本
const getLocatorStatusLabel = (status: string) => {
  return LOCATOR_STATUS_MAP[status]?.label || status
}

// 格式化定位覆盖率显示
const formatLocatorCoverage = (coverage: number | string): string => {
  if (typeof coverage === 'number') {
    return `${coverage.toFixed(1)}%`
  }
  // 如果已经是字符串（比如"85.5%"），直接返回
  if (typeof coverage === 'string' && coverage.endsWith('%')) {
    return coverage
  }
  return `${coverage}%`
}

// ==================== 前置条件步骤相关方法 ====================

/** AI解析前置条件，生成可执行步骤 */
const parsePrecondition = async () => {
  if (!caseId.value) return
  parsePreconditionLoading.value = true
  try {
    const res = await testCaseViewApi.parsePrecondition(caseId.value)
    const data = (res as any).data
    if (data) {
      const steps = Array.isArray(data) ? data : []
      if (steps.length > 0) {
        ElMessage.success(`AI解析成功，生成 ${steps.length} 个步骤`)
        if (technicalViewData.value) {
          technicalViewData.value.precondition_steps = steps
        }
      } else {
        ElMessage.info('AI未解析出可执行步骤')
      }
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'AI解析失败')
  } finally {
    parsePreconditionLoading.value = false
  }
}

/** 手动添加一个前置条件步骤 */
const addPreconditionStep = () => {
  if (!technicalViewData.value) return
  const steps = [...(technicalViewData.value.precondition_steps || [])]
  steps.push({
    step_number: steps.length + 1,
    action: '新步骤',
    expected_result: '',
    action_type: 'click',
    input_value: '',
    target_element: '',
    has_locator: false,
    locator_status: 'pending',
  })
  technicalViewData.value.precondition_steps = steps
  savePreconditionSteps(steps)
}

/** 删除指定索引的前置条件步骤 */
const deletePreconditionStep = async (index: number) => {
  if (!technicalViewData.value) return
  const steps = [...(technicalViewData.value.precondition_steps || [])]
  steps.splice(index, 1)
  // 重新编号
  steps.forEach((s: any, i: number) => {
    s.step_number = i + 1
  })
  await savePreconditionSteps(steps)
  technicalViewData.value.precondition_steps = steps
}

/** 批量保存前置条件步骤到后端 */
const savePreconditionSteps = async (steps: any[]) => {
  if (!caseId.value) return
  try {
    await testCaseViewApi.batchSavePreconditionSteps(caseId.value, { steps })
  } catch (e: any) {
    ElMessage.error('保存前置条件步骤失败')
  }
}

/** 获取操作类型对应的Tag颜色 */
const getActionTypeTagType = (actionType: string) => {
  const map: Record<string, string> = {
    click: 'primary',
    input: 'success',
    navigate: 'warning',
    verify: 'info',
    select: 'success',
    wait: 'info',
    hover: '',
    scroll: 'info',
    refresh: 'info',
    keypress: 'info',
  }
  return map[actionType] || 'info'
}

// 返回
const goBack = () => {
  router.push('/home/case')
}

// 获取步骤行样式类名（高亮失败步骤）
const getStepRowClass = ({ rowIndex }: { row: any; rowIndex: number }) => {
  if (isCorrectionMode.value && rowIndex === correctionStepIndex.value) {
    return 'highlighted-step'
  }
  return ''
}

// 开始单元格编辑
const startCellEdit = (stepIndex: number, field: string, value: any) => {
  if (issueType.value === 'product_bug') return
  editingCell.value = { stepIndex, field }
  editingValue.value = value || ''
}

// 取消单元格编辑
const cancelCellEdit = () => {
  editingCell.value = null
  editingValue.value = ''
}

// 保存单元格编辑
const saveCellEdit = async () => {
  if (!editingCell.value || !technicalViewData.value) return

  const { stepIndex, field } = editingCell.value
  const step = technicalViewData.value.steps[stepIndex]
  if (!step) return

  if (!editingValue.value.trim() && (field === 'action' || field === 'expected_result')) {
    ElMessage.warning('内容不能为空')
    return
  }

  cellSaving.value = true
  try {
    const stepId = step.step_id || step.step_number

    if (field === 'action' || field === 'expected_result') {
      const stepsPayload = technicalViewData.value.steps.map((s, i) => ({
        step_number: s.step_number,
        action: i === stepIndex && field === 'action' ? editingValue.value : s.action || '',
        expected_result:
          i === stepIndex && field === 'expected_result'
            ? editingValue.value
            : s.expected_result || '',
      }))
      await testCaseApi.updateCase(caseId.value, { steps: stepsPayload })
    } else if (field === 'css_selector' || field === 'xpath') {
      await testCaseApi.updateStepLocator(caseId.value, stepId, {
        [field]: editingValue.value,
      })
    }

    if (field === 'action') step.action = editingValue.value
    else if (field === 'expected_result') step.expected_result = editingValue.value
    else if (field === 'css_selector' && step.locator)
      step.locator.css_selector = editingValue.value
    else if (field === 'xpath' && step.locator) step.locator.xpath = editingValue.value

    ElMessage.success('保存成功')
    editingCell.value = null
    editingValue.value = ''
  } catch (error: any) {
    console.error('保存失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    cellSaving.value = false
  }
}

// 处理纠正入口参数
const handleCorrectionParams = async () => {
  const query = route.query
  if (query.correction === 'true') {
    isCorrectionMode.value = true
    correctionStepIndex.value = Number(query.stepIndex) || -1
    issueType.value = (query.issueType as any) || 'case_issue'
    failureReason.value = query.failureReason
      ? decodeURIComponent(query.failureReason as string)
      : ''
    aiAnalysisText.value = query.aiAnalysis ? decodeURIComponent(query.aiAnalysis as string) : ''

    if (issueType.value === 'product_bug') {
      isEditing.value = false
    }

    currentView.value = VIEW_TYPES.TECHNICAL
    await fetchTechnicalView()

    if (issueType.value !== 'product_bug' && caseId.value) {
      try {
        await testCaseApi.startCorrection(caseId.value)
      } catch (error: any) {
        console.error('设置纠正状态失败:', error)
      }
    }

    await nextTick()
    const highlightedRow = document.querySelector('.highlighted-step')
    if (highlightedRow) {
      highlightedRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
}

// 打开快速验证对话框
const openQuickVerify = () => {
  if (!technicalViewData.value) return
  selectedVerifySteps.value = technicalViewData.value.steps.map((s) => s.step_number)
  quickVerifyVisible.value = true
}

// 执行快速验证
const executeQuickVerify = async () => {
  if (selectedVerifySteps.value.length === 0) {
    ElMessage.warning('请至少选择一个步骤')
    return
  }

  quickVerifyLoading.value = true
  try {
    await createQuickVerify(caseId.value, selectedVerifySteps.value)
    await testCaseApi.submitVerification(caseId.value)
    ElMessage.success('快速验证任务已创建，即将跳转到执行页面')
    quickVerifyVisible.value = false
    router.push('/home/execution/' + caseId.value)
  } catch (error: any) {
    console.error('创建快速验证任务失败:', error)
    ElMessage.error(error.response?.data?.detail || '创建快速验证任务失败')
  } finally {
    quickVerifyLoading.value = false
  }
}

// 打开版本历史
const openVersionHistory = () => {
  versionHistoryVisible.value = true
  versionPage.value = 1
  fetchVersionHistory()
}

// 获取版本历史列表
const fetchVersionHistory = async () => {
  if (!caseId.value) return
  versionLoading.value = true
  try {
    const res = await testCaseApi.getCaseVersions(caseId.value, versionPage.value, 20)
    const data = res
    versionList.value = data.items || []
    versionTotal.value = data.total || versionList.value.length
  } catch (error: any) {
    console.error('获取版本历史失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取版本历史失败')
  } finally {
    versionLoading.value = false
  }
}

// 回滚到指定版本
const handleRollback = async (version: any) => {
  rollbackLoading.value = true
  try {
    await testCaseApi.rollbackCaseVersion(caseId.value, version.id)
    ElMessage.success(`已回滚到版本 v${version.version_number}`)
    versionHistoryVisible.value = false
    await fetchCaseDetail()
    if (currentView.value === VIEW_TYPES.TECHNICAL) {
      await fetchTechnicalView()
    }
  } catch (error: any) {
    console.error('回滚失败:', error)
    ElMessage.error(error.response?.data?.detail || '回滚失败')
  } finally {
    rollbackLoading.value = false
  }
}

// 打开添加定位对话框
const openAddLocator = (stepIndex: number, _row: any) => {
  addLocatorStepIndex.value = stepIndex
  addLocatorForm.value = {
    css_selector: '',
    xpath: '',
    ai_coordinate: '',
    locator_type: 'css',
  }
  addLocatorVisible.value = true
}

// 保存添加定位
const saveAddLocator = async () => {
  if (!technicalViewData.value) return
  const step = technicalViewData.value.steps[addLocatorStepIndex.value]
  if (!step) return

  const { css_selector, xpath, ai_coordinate } = addLocatorForm.value
  if (!css_selector && !xpath && !ai_coordinate) {
    ElMessage.warning('请至少填写一种定位信息')
    return
  }

  addLocatorLoading.value = true
  try {
    const stepId = step.step_id || step.step_number
    await testCaseApi.updateStepLocator(caseId.value, stepId, {
      css_selector,
      xpath,
      ai_coordinate,
    })

    if (!step.locator) {
      step.locator = {}
    }
    if (css_selector) step.locator.css_selector = css_selector
    if (xpath) step.locator.xpath = xpath
    step.locator_status = 'recorded'

    ElMessage.success('定位信息添加成功')
    addLocatorVisible.value = false
  } catch (error: any) {
    console.error('添加定位失败:', error)
    ElMessage.error(error.response?.data?.detail || '添加定位失败')
  } finally {
    addLocatorLoading.value = false
  }
}

// 页面加载
onMounted(async () => {
  if (caseId.value) {
    await fetchCaseDetail()
    await handleCorrectionParams()
  }
})
</script>

<style scoped lang="scss">
.case-detail {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      color: #303133;
    }
  }

  .header-right {
    display: flex;
    gap: 12px;
  }
}

.loading-container,
.empty-container {
  padding: 60px 0;
}

.case-content {
  .info-section {
    margin-bottom: 30px;
  }

  .bug-warning-alert {
    margin-bottom: 20px;
  }

  .correction-alert {
    margin-bottom: 20px;
  }

  .quick-verify-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding: 12px 16px;
    background: #f0f9eb;
    border-radius: 8px;
    border: 1px solid #e1f3d8;

    .verify-hint {
      color: #67c23a;
      font-size: 13px;
    }
  }

  .suggestion-panel {
    margin-top: 16px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;

    .suggestion-header {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 10px 16px;
      background: #fdf6ec;
      font-weight: 600;
      font-size: 14px;
      color: #e6a23c;

      .el-button {
        margin-left: auto;
      }
    }

    .suggestion-body {
      padding: 12px 16px;
      font-size: 13px;
      line-height: 1.8;

      .suggestion-item {
        margin-bottom: 8px;

        p {
          margin: 4px 0;
          color: #606266;
        }
      }
    }
  }

  .section {
    margin-bottom: 30px;

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .section-title {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      padding-bottom: 8px;
      border-bottom: 2px solid #409eff;
    }

    .static-content {
      padding: 16px;
      background-color: #f5f7fa;
      border-radius: 4px;
      line-height: 1.6;
      color: #606266;
      min-height: 60px;
      white-space: pre-wrap;
    }

    .editable-content {
      :deep(.el-textarea__inner) {
        resize: none;
      }
    }
  }

  .case-no {
    font-family: 'Courier New', monospace;
    font-weight: 600;
    color: #409eff;
  }

  .case-title {
    font-weight: 500;
  }

  .steps-view {
    .step-index {
      font-weight: 600;
      color: #409eff;
    }

    .step-content {
      line-height: 1.6;
      color: #606266;
      white-space: pre-wrap;
    }

    .coverage-info {
      margin-bottom: 16px;
      display: flex;
      align-items: center;
    }

    .test-data-item {
      display: flex;
      align-items: center;
      margin-bottom: 4px;
      font-size: 12px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .test-data-value {
      color: #606266;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .steps-editor {
    .step-item {
      background: #fafbfc;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;

      .step-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .step-number {
          font-weight: 600;
          color: #409eff;
          font-size: 14px;
        }
      }

      .step-fields {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }

      .step-field {
        label {
          display: block;
          font-size: 12px;
          color: #909399;
          margin-bottom: 4px;
          font-weight: 500;
        }
      }
    }
  }

  .save-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    padding-top: 20px;
    border-top: 1px solid #ebeef5;
  }
}

:deep(.highlighted-step) {
  background-color: #fdf6ec !important;
  border-left: 3px solid #e6a23c;
}

.cell-display {
  display: flex;
  align-items: center;
  cursor: pointer;
  min-height: 28px;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background-color 0.2s;

  &:hover {
    background-color: #f5f7fa;

    .edit-icon {
      opacity: 1;
    }
  }

  span {
    flex: 1;
    word-break: break-all;
  }

  .edit-icon {
    opacity: 0;
    color: #409eff;
    font-size: 14px;
    margin-left: 4px;
    transition: opacity 0.2s;
  }
}

.cell-editing {
  :deep(.el-input--small .el-input__wrapper) {
    min-height: 30px;
  }

  .cell-actions {
    display: flex;
    gap: 4px;
    margin-top: 4px;

    :deep(.el-button--small) {
      min-height: 30px;
      padding: 5px 10px;
    }
  }
}

.version-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
