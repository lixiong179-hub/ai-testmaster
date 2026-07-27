<template>
  <div class="smart-generate-container">
    <div class="page-header">
      <h2>智能生成用例</h2>
      <el-button @click="handleBack"
        ><el-icon><ArrowLeft /></el-icon>返回</el-button
      >
    </div>
    <!-- Task2: 8 步合并为 4 步 -->
    <el-steps :active="stepIndex" finish-status="success" class="steps-indicator" align-center>
      <el-step title="选择任务" />
      <el-step title="选择资料" />
      <el-step title="生成用例" />
      <el-step title="预览结果" />
    </el-steps>
    <div class="step-content">
      <!-- Step 1: 选任务（点卡片即确认 task，不再分离"进入生成"动作） -->
      <div v-if="store.currentStep === 'task'" class="task-select">
        <div class="task-cards">
          <div
            class="task-card primary"
            :class="{ active: store.selectedTask === 'new_feature' }"
            @click="selectTask('new_feature')"
          >
            <div class="task-icon"><el-icon :size="40"><MagicStick /></el-icon></div>
            <h3>新功能生成用例</h3>
            <p>我有新需求或测试点，要生成测试用例</p>
            <div class="task-tags">
              <el-tag size="small">需求文档</el-tag><el-tag size="small">测试点</el-tag
              ><el-tag size="small" type="info">UI原型（可选）</el-tag>
            </div>
            <div class="task-btn-hint">点击卡片即选择此任务</div>
          </div>
          <div
            class="task-card"
            :class="{ active: store.selectedTask === 'history_update' }"
            @click="selectTask('history_update')"
          >
            <div class="task-icon"><el-icon :size="40"><Document /></el-icon></div>
            <h3>历史资产更新用例</h3>
            <p>我有旧用例，要基于新版本更新</p>
            <div class="task-tags">
              <el-tag size="small" type="info">Excel</el-tag
              ><el-tag size="small" type="info">XMind</el-tag
              ><el-tag size="small" type="info">保鲜建议</el-tag>
            </div>
            <div class="task-btn-hint">点击卡片即选择此任务</div>
          </div>
          <div class="task-card disabled">
            <div class="task-icon"><el-icon :size="40"><Download /></el-icon></div>
            <h3>导入测试资产</h3>
            <p>我只想先把旧资产导入系统</p>
            <div class="task-tags">
              <el-tag size="small" type="info">Excel</el-tag
              ><el-tag size="small" type="info">XMind</el-tag>
            </div>
            <el-button class="task-btn" @click="goToTestPointManagement">前往测试点管理</el-button>
          </div>
        </div>
      </div>

      <!-- Step 2: 选资料 + 识别结果 + 策略推荐（合并原 context/strategy 两步） -->
      <div v-else-if="store.currentStep === 'material'" class="material-select">
        <el-form label-width="100px" class="material-form">
          <el-form-item label="项目" required>
            <el-select
              v-model="store.selectedProjectId"
              placeholder="选择项目"
              filterable
              style="width: 100%"
            >
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求文件">
            <el-select
              v-model="store.requirementFileIds"
              multiple
              placeholder="选择需求文件（可选）"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="f in requirementFiles"
                :key="f.id"
                :label="f.file_name || f.original_name"
                :value="f.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="测试点" required>
            <el-select
              v-model="store.testPointIds"
              multiple
              placeholder="选择测试点"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="tp in testPoints"
                :key="tp.id"
                :label="`${tp.module || ''} - ${tp.name || tp.test_point || ''}`"
                :value="tp.id"
              />
            </el-select>
            <!-- Task12: 测试点空提示改为 el-empty + 引导按钮 -->
            <div v-if="testPoints.length === 0 && store.selectedProjectId" class="empty-block">
              <el-empty description="暂无测试点" :image-size="60">
                <el-button type="primary" @click="goToTestPointManagement">去提取测试点</el-button>
              </el-empty>
            </div>
          </el-form-item>
          <el-form-item label="UI原型项目">
            <div class="ui-project-row">
              <el-select
                v-model="store.selectedUIPrototypeProjectId"
                placeholder="选择已有原型项目（可选）"
                filterable
                clearable
                style="flex: 1"
                @change="store.handleUIPrototypeProjectChange"
              >
                <el-option
                  v-for="p in store.uiPrototypeProjects"
                  :key="p.id"
                  :label="p.name"
                  :value="p.id"
                >
                  <span>{{ p.name }}</span
                  ><el-tag size="small" type="info" style="margin-left: 8px"
                    >{{ p.screen_count || 0 }} 页</el-tag
                  >
                </el-option>
              </el-select>
              <el-button size="default" @click="store.uiUploadDialogVisible = true"
                ><el-icon><Upload /></el-icon>上传UI页面</el-button
              >
            </div>
            <div class="optional-hint">
              UI原型图可选，不提供也能继续生成。可直接上传截图，无需先创建原型项目
            </div>
          </el-form-item>
          <el-form-item v-if="store.selectedTask === 'history_update'" label="历史资产">
            <div class="history-asset-section">
              <div class="history-upload-row">
                <el-upload
                  action=""
                  :auto-upload="false"
                  :show-file-list="false"
                  accept=".xlsx,.xls,.xmind"
                  :on-change="handleHistoryAssetFileChange"
                >
                  <el-button size="default"
                    ><el-icon><Upload /></el-icon>上传Excel/XMind</el-button
                  >
                </el-upload>
                <el-button size="default" @click="systemCaseSelectDialogVisible = true"
                  >从系统用例导入</el-button
                >
              </div>
              <div v-if="store.historyAssets.length > 0" class="history-asset-list">
                <div
                  v-for="asset in store.historyAssets"
                  :key="asset.id"
                  class="history-asset-item"
                >
                  <el-checkbox
                    :model-value="store.selectedHistoryAssetIds.includes(asset.id)"
                    @change="toggleHistoryAsset(asset.id)"
                  />
                  <span class="asset-filename">{{
                    asset.original_filename || '系统用例导入'
                  }}</span>
                  <el-tag
                    size="small"
                    :type="
                      asset.asset_type === 'excel'
                        ? 'success'
                        : asset.asset_type === 'xmind'
                          ? 'warning'
                          : 'info'
                    "
                    >{{ assetTypeLabel(asset.asset_type) }}</el-tag
                  >
                  <el-tag size="small" type="info">{{ asset.case_count }} 条用例</el-tag>
                  <el-tag
                    size="small"
                    :type="
                      asset.parse_status === 'completed'
                        ? 'success'
                        : asset.parse_status === 'failed'
                          ? 'danger'
                          : asset.parse_status === 'parsing'
                            ? 'warning'
                            : 'info'
                    "
                    >{{ historyParseStatusLabel(asset.parse_status) }}</el-tag
                  >
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click="store.removeHistoryAsset(asset.id)"
                    >移除</el-button
                  >
                </div>
              </div>
              <!-- Task12: 历史资产空提示改为 el-empty + 引导按钮 -->
              <div v-else class="empty-block">
                <el-empty description="暂无历史资产" :image-size="60">
                  <el-button type="primary" @click="systemCaseSelectDialogVisible = true"
                    >上传历史资产</el-button
                  >
                </el-empty>
              </div>
            </div>
          </el-form-item>
        </el-form>
        <div v-if="store.uiScreenDetails.length > 0" class="ui-screen-section">
          <div class="ui-screen-header">
            <h4>UI页面选择</h4>
            <div class="ui-screen-actions">
              <el-button
                v-if="unparsedScreenIds.length > 0"
                size="small"
                type="warning"
                :loading="store.uiParsing === true"
                @click="store.parseUIScreens(unparsedScreenIds)"
                >解析待处理页面 ({{ unparsedScreenIds.length }})</el-button
              >
              <!-- Task7/12: uiParsing 超时状态显示重试按钮 -->
              <el-button
                v-if="store.uiParsing === 'timeout'"
                size="small"
                type="primary"
                @click="store.parseUIScreens(unparsedScreenIds)"
                >重试解析</el-button
              >
            </div>
          </div>
          <el-alert
            v-if="store.hasUIParseFailure"
            type="warning"
            :closable="false"
            show-icon
            class="ui-parse-alert"
          >
            <template #title
              >部分 UI 页面解析失败，不影响生成，但相关步骤需人工确认页面元素</template
            >
          </el-alert>
          <el-alert
            v-if="store.hasUIParsePending"
            type="info"
            :closable="false"
            show-icon
            class="ui-parse-alert"
          >
            <template #title>部分 UI 页面尚未解析，建议先解析以获得更准确的页面元素信息</template>
          </el-alert>
          <div class="ui-screen-grid">
            <div
              v-for="screen in store.uiScreenDetails"
              :key="screen.id"
              class="ui-screen-card"
              :class="{
                selected: store.uiScreenIds.includes(screen.id),
                'parse-failed': screen.parse_status === 'failed',
                'parse-pending':
                  screen.parse_status === 'pending' || screen.parse_status === 'running',
              }"
              @click="store.toggleUIScreen(screen.id)"
            >
              <div class="screen-thumb">
                <img
                  v-if="store.uiScreenImageUrls[screen.id]"
                  :src="store.uiScreenImageUrls[screen.id]"
                  :alt="screen.screen_name"
                />
                <el-icon v-else :size="32" color="var(--color-text-disabled)"><Picture /></el-icon>
              </div>
              <div class="screen-info">
                <span class="screen-name">{{ screen.screen_name || `页面${screen.id}` }}</span>
                <el-tag
                  size="small"
                  :type="
                    screen.parse_status === 'completed'
                      ? 'success'
                      : screen.parse_status === 'failed'
                        ? 'danger'
                        : 'info'
                  "
                  >{{ parseStatusLabel(screen.parse_status) }}</el-tag
                >
              </div>
              <div v-if="screen.parse_status === 'completed'" class="screen-elements">
                {{ screen.element_count || 0 }} 元素 / {{ screen.button_count || 0 }} 按钮
              </div>
              <div v-if="screen.parse_status === 'failed'" class="screen-error">
                {{ screen.parse_error || '解析失败' }}
              </div>
            </div>
          </div>
        </div>
        <el-collapse class="advanced-collapse">
          <el-collapse-item title="高级配置" name="advanced">
            <el-form label-width="100px" size="small">
              <el-form-item label="用例类型"
                ><el-select v-model="store.advancedConfig.case_type"
                  ><el-option label="手工用例" value="manual" /><el-option
                    label="UI自动化"
                    value="ui_automation" /><el-option
                    label="API自动化"
                    value="api_automation" /></el-select
              ></el-form-item>
              <el-form-item label="执行模式"
                ><el-select v-model="store.advancedConfig.exec_mode"
                  ><el-option label="手工执行" value="manual" /><el-option
                    label="全部"
                    value="all" /></el-select
              ></el-form-item>
              <el-form-item label="默认优先级"
                ><el-select v-model="store.advancedConfig.priority"
                  ><el-option label="高" :value="1" /><el-option label="中" :value="2" /><el-option
                    label="低"
                    :value="3" /></el-select
              ></el-form-item>
              <el-form-item label="生成模式"
                ><el-select v-model="store.advancedConfig.mode"
                  ><el-option label="线性模式" value="linear" /><el-option
                    label="图谱模式"
                    value="graph" /></el-select
              ></el-form-item>
            </el-form>
          </el-collapse-item>
        </el-collapse>

        <!-- Task2/9: 资料识别阶段骨架屏（等待 generate-context 返回） -->
        <el-card v-if="contextLoading" class="context-card">
          <el-skeleton :rows="5" animated />
        </el-card>

        <!-- Task2: 识别结果与策略推荐同屏展示（合并原 context/strategy 两步） -->
        <template v-if="!contextLoading && store.generationContext">
          <el-card class="context-card">
            <template #header
              ><div class="card-header">
                <span>资料识别结果</span
                ><el-tag :type="materialLevelType">{{ store.materialLevelText }}</el-tag>
              </div></template
            >
            <el-descriptions :column="2" border>
              <el-descriptions-item label="需求命中"
                >{{
                  (store.contextStats.requirements_used as number) || 0
                }}
                条</el-descriptions-item
              >
              <el-descriptions-item label="测试点数量"
                >{{
                  (store.contextStats.test_points_loaded as number) || 0
                }}
                个</el-descriptions-item
              >
              <el-descriptions-item label="UI页面命中"
                >{{ (store.contextStats.ui_screens_used as number) || 0 }} 页</el-descriptions-item
              >
              <el-descriptions-item label="历史参考"
                >{{
                  (store.contextStats.history_cases_used as number) || 0
                }}
                条</el-descriptions-item
              >
              <el-descriptions-item label="完整度评分"
                ><el-progress
                  :percentage="(store.contextStats.completeness_score as number) || 0"
                  :stroke-width="12"
              /></el-descriptions-item>
              <el-descriptions-item label="低可信过滤"
                >{{
                  (store.contextStats.history_low_trust_filtered as number) || 0
                }}
                条</el-descriptions-item
              >
            </el-descriptions>
          </el-card>
          <el-card v-if="store.evidenceRefsDisplay.length > 0" class="evidence-card">
            <template #header><span>来源依据</span></template>
            <div v-for="ref in store.evidenceRefsDisplay" :key="ref.type" class="evidence-group">
              <el-tag
                size="small"
                :type="
                  ref.type === 'requirement' ? undefined : ref.type === 'ui' ? 'success' : 'info'
                "
                >{{ ref.label }}</el-tag
              >
              <span v-for="(item, i) in ref.items" :key="i" class="evidence-item">{{ item }}</span>
            </div>
          </el-card>
          <el-card v-if="store.uiScreenMatchResults.length > 0" class="ui-match-card">
            <template #header><span>UI 页面匹配结果</span></template>
            <el-table :data="store.uiScreenMatchResults" size="small" stripe>
              <el-table-column prop="screen_name" label="页面名称" />
              <el-table-column prop="confidence" label="匹配置信度" width="140">
                <template #default="{ row }"
                  ><el-tag
                    size="small"
                    :type="
                      row.confidence === 'explicit'
                        ? 'success'
                        : row.confidence === 'matched'
                          ? 'primary'
                          : 'info'
                    "
                    >{{ confidenceLabel(row.confidence) }}</el-tag
                  ></template
                >
              </el-table-column>
              <el-table-column prop="element_count" label="识别元素" width="100" />
            </el-table>
          </el-card>
          <el-card v-if="store.warnings.length > 0" class="warning-card">
            <template #header><span>风险提示</span></template>
            <div v-for="w in store.warningUserTexts" :key="w.code" class="warning-item">
              <el-icon color="var(--color-warning)"><WarningFilled /></el-icon><span>{{ w.text }}</span>
            </div>
          </el-card>
          <el-card
            v-if="store.selectedTask === 'history_update' && store.historyClassification"
            class="classification-card"
          >
            <template #header><span>历史资产分类摘要</span></template>
            <div class="classification-summary">
              <el-tag type="success" size="large"
                >可复用 {{ store.historyClassification.summary.reuse_count }}</el-tag
              >
              <el-tag type="warning" size="large"
                >建议修改 {{ store.historyClassification.summary.update_count }}</el-tag
              >
              <el-tag size="large">新增 {{ store.historyClassification.summary.new_count }}</el-tag>
              <el-tag type="danger" size="large"
                >可能废弃 {{ store.historyClassification.summary.deprecated_count }}</el-tag
              >
              <el-tag type="info" size="large"
                >待确认 {{ store.historyClassification.summary.confirm_required_count }}</el-tag
              >
            </div>
            <div class="classification-total">
              共 {{ store.historyClassification.summary.total }} 条
            </div>
          </el-card>
          <!-- Task2: 推荐策略与识别结果同屏展示 -->
          <el-card class="strategy-card">
            <template #header><span>推荐生成策略</span></template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="策略">{{
                store.strategyDisplayText
              }}</el-descriptions-item>
              <el-descriptions-item label="依据">{{
                store.scenarioType === 'A1_REQUIREMENT_TESTPOINT_UI'
                  ? '需求 + 测试点 + UI'
                  : '需求 + 测试点'
              }}</el-descriptions-item>
              <el-descriptions-item label="重点">{{
                store.scenarioType === 'A1_REQUIREMENT_TESTPOINT_UI'
                  ? '功能、异常、边界、页面交互、元素校验'
                  : '功能、异常、边界、权限、状态、数据校验'
              }}</el-descriptions-item>
              <el-descriptions-item v-if="store.uiScreenIds.length === 0" label="风险"
                ><el-text type="warning"
                  >UI 元素和页面布局需要人工确认</el-text
                ></el-descriptions-item
              >
            </el-descriptions>
          </el-card>
        </template>

        <!-- Task8.1/12: 识别失败错误状态（透出真实原因 + 重试按钮） -->
        <el-card v-if="contextError" class="context-card">
          <ErrorState
            title="资料识别失败"
            :reason="contextError"
            retryable
            @retry="handleAnalyzeContext"
          />
        </el-card>

        <div class="step-actions">
          <el-button @click="store.currentStep = 'task'">返回</el-button>
          <el-button
            v-if="!store.generationContext"
            type="primary"
            :disabled="!canAnalyzeContext"
            :loading="contextLoading"
            @click="handleAnalyzeContext"
            >分析资料</el-button
          >
          <el-button v-else type="primary" size="large" @click="handleStartGeneration"
            >开始生成</el-button
          >
        </div>
      </div>

      <!-- Step 3: 生成中（真实进度 + 骨架屏 + 真中断取消） -->
      <div v-else-if="store.currentStep === 'generating'" class="generating-progress">
        <el-card v-if="store.generating">
          <div class="progress-content">
            <el-icon class="spin-icon" :size="48" color="var(--color-primary)"><Loading /></el-icon>
            <h3>{{ store.generationProgress || '正在生成...' }}</h3>
            <!-- Task3.2: 真实进度百分比（progressPercent 为 null 时降级 indeterminate） -->
            <el-progress
              :percentage="store.progressPercent ?? 100"
              :indeterminate="store.progressPercent === null"
              :stroke-width="8"
            />
            <!-- Task3.2: 显示 "已生成 X/Y" 文本 -->
            <p class="progress-hint">
              已生成 {{ store.previewCases.length
              }}{{ store.sseTotalCount > 0 ? ` / ${store.sseTotalCount}` : '' }} 条用例
            </p>
            <!-- Task9: 等待首个 SSE 事件时骨架屏占位预览区 -->
            <div v-if="store.previewCases.length === 0" class="preview-skeleton">
              <el-skeleton :rows="8" animated />
            </div>
          </div>
        </el-card>
        <!-- Task8.1/12: 生成失败错误状态（透出真实原因 + 重试按钮） -->
        <el-card v-else>
          <ErrorState
            v-if="generationFailed"
            title="生成未完成"
            :reason="store.generationProgress"
            retryable
            @retry="handleRetryGeneration"
          >
            <template #extra-actions>
              <el-button @click="store.currentStep = 'material'">返回修改资料</el-button>
              <el-button @click="handleReset">重新开始</el-button>
            </template>
          </ErrorState>
          <el-result v-else icon="info" title="已取消生成" sub-title="已生成的部分用例已保留">
            <template #extra>
              <el-button
                v-if="store.previewCases.length > 0"
                type="primary"
                @click="store.currentStep = 'preview'"
                >查看已生成用例</el-button
              >
              <el-button @click="handleRetryGeneration">重新生成</el-button>
              <el-button @click="store.currentStep = 'material'">返回修改资料</el-button>
            </template>
          </el-result>
        </el-card>
        <!-- Task4.2: 取消按钮调用 store.abortGeneration() 真中断 -->
        <div class="step-actions">
          <el-button v-if="store.generating" @click="handleCancelGeneration">取消生成</el-button>
        </div>
      </div>

      <!-- Step 4: 预览结果 + 保存确认（合并原 preview/save_confirm/save_result） -->
      <div v-else-if="store.currentStep === 'preview'" class="preview-results">
        <!-- Task9: 保存后跳转前骨架屏占位 -->
        <el-card v-if="store.saving" class="save-skeleton-card">
          <el-skeleton :rows="6" animated />
        </el-card>
        <template v-else>
          <div v-if="store.selectedTask !== 'history_update'" class="preview-summary-row">
            <!-- Task11: 质量分布环形图（点击扇区过滤） -->
            <QualityDonutChart
              :passed="store.passedCount"
              :warning="store.warningCount"
              :pending-review="store.pendingReviewCount"
              :rejected="store.rejectedCount"
              :active-filter="qualityFilter"
              @select="handleQualityFilter"
            />
          </div>
          <div
            v-if="store.selectedTask === 'history_update' && store.historyClassification"
            class="preview-summary"
          >
            <el-tag type="success"
              >可复用 {{ store.historyClassification.summary.reuse_count }}</el-tag
            >
            <el-tag type="warning"
              >建议修改 {{ store.historyClassification.summary.update_count }}</el-tag
            >
            <el-tag>新增 {{ store.historyClassification.summary.new_count }}</el-tag>
            <el-tag type="danger"
              >可能废弃 {{ store.historyClassification.summary.deprecated_count }}</el-tag
            >
            <el-tag type="info"
              >待确认 {{ store.historyClassification.summary.confirm_required_count }}</el-tag
            >
          </div>
          <div v-if="store.selectedTask !== 'history_update'" class="preview-toolbar">
            <el-checkbox
              v-model="isAllSelected"
              :indeterminate="isIndeterminate"
              @change="handleToggleAll"
              >全选</el-checkbox
            >
            <el-button
              size="small"
              type="danger"
              plain
              :disabled="selectedCaseCount === 0"
              @click="handleBatchDelete"
              >批量删除 ({{ selectedCaseCount }})</el-button
            >
            <el-button
              size="small"
              type="primary"
              plain
              :disabled="selectedCaseCount === 0"
              :loading="batchRegenerating"
              @click="handleBatchRegenerate"
              >批量重新生成 ({{ selectedCaseCount }})</el-button
            >
            <el-button
              v-if="batchRegenerating"
              size="small"
              type="warning"
              plain
              @click="handleCancelBatchRegenerate"
              >取消重生成</el-button
            >
            <el-tag v-if="qualityFilter" size="small" closable @close="qualityFilter = null"
              >过滤: {{ qualityLabel(qualityFilter) }}</el-tag
            >
          </div>
          <el-collapse class="coverage-collapse">
            <el-collapse-item title="覆盖摘要" name="coverage">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="总用例数">{{
                  store.coverageSummary.total
                }}</el-descriptions-item>
                <el-descriptions-item label="分类分布"
                  ><el-tag
                    v-for="(count, cat) in store.coverageSummary.byCategory"
                    :key="cat as string"
                    size="small"
                    class="coverage-tag"
                    >{{ cat }}: {{ count }}</el-tag
                  ></el-descriptions-item
                >
                <el-descriptions-item label="测试点覆盖" :span="2"
                  ><el-tag
                    v-for="(count, tp) in store.coverageSummary.byTestPoint"
                    :key="tp as string"
                    size="small"
                    type="info"
                    class="coverage-tag"
                    >{{ tp }}: {{ count }}条</el-tag
                  ></el-descriptions-item
                >
              </el-descriptions>
            </el-collapse-item>
          </el-collapse>

          <!-- Task2: 预览页直接含保存按钮区（合并原 save_confirm） -->
          <el-card v-if="store.selectedTask !== 'history_update'" class="save-confirm-card">
            <el-alert type="warning" :closable="false" show-icon class="save-alert">
              <template #title>当前只是生成预览，尚未入库。点击保存后才会写入用例库。</template>
            </el-alert>
            <el-descriptions :column="1" border size="small" class="save-summary">
              <el-descriptions-item label="本次将保存">
                <el-tag type="success">可直接保存 {{ store.passedCount }} 条</el-tag>
                <el-tag type="warning"
                  >需要确认 {{ store.warningCount + store.pendingReviewCount }} 条</el-tag
                >
                <el-tag type="danger">不建议保存 {{ store.rejectedCount }} 条</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="已选中保存"
                >{{ store.selectedForSaveCount }} 条</el-descriptions-item
              >
            </el-descriptions>
            <div class="save-mode-select">
              <h4>保存方式</h4>
              <el-radio-group v-model="saveMode">
                <el-radio value="draft">保存为草稿（推荐）</el-radio>
                <el-radio value="formal">保存为正式用例</el-radio>
                <el-radio value="passed_only">仅保存已通过项</el-radio>
              </el-radio-group>
              <p v-if="saveMode === 'formal'" class="save-warning">
                当前结果由 AI
                生成，建议先保存为草稿并人工复核。如保存为正式用例，请确认步骤、预期结果和来源依据均已核对。
              </p>
            </div>
          </el-card>

          <!-- 历史资产分类用例 -->
          <template v-if="store.selectedTask === 'history_update' && store.historyClassification">
            <div
              v-for="group in historyClassificationGroups"
              :key="group.key"
              class="classification-group"
            >
              <div class="group-header" :class="`group-${group.key}`">
                <el-tag :type="group.tagType" size="large"
                  >{{ group.label }} ({{ group.items.length }})</el-tag
                >
                <span class="group-action-hint">{{ group.actionHint }}</span>
              </div>
              <el-card
                v-for="item in group.items"
                :key="item.client_id"
                class="preview-case-card"
                :class="`classification-${group.key}`"
              >
                <div class="case-header">
                  <el-checkbox
                    v-model="item._selectedForSave"
                    @change="onHistoryItemSelectChange(item)"
                  />
                  <span class="case-title">{{
                    item.suggested_case?.title || item.history_case?.title || '未命名'
                  }}</span>
                  <el-tag :type="group.tagType" size="small">{{ group.label }}</el-tag>
                  <span v-if="item.confidence < 0.8" class="confidence-hint"
                    >置信度: {{ (item.confidence * 100).toFixed(0) }}%</span
                  >
                  <span class="classification-reason">{{ item.reason }}</span>
                </div>
                <template
                  v-if="group.key === 'UPDATE_CASE' && item.history_case && item.suggested_case"
                >
                  <div class="diff-compare">
                    <div class="diff-side diff-old">
                      <h5>历史用例</h5>
                      <div class="diff-field">
                        <strong>标题：</strong>{{ item.history_case.title }}
                      </div>
                      <div class="diff-field">
                        <strong>模块：</strong>{{ item.history_case.module }}
                      </div>
                      <div class="diff-field">
                        <strong>前置条件：</strong>{{ item.history_case.precondition }}
                      </div>
                      <div class="diff-field">
                        <strong>预期结果：</strong>{{ item.history_case.expected_result }}
                      </div>
                    </div>
                    <div class="diff-side diff-new">
                      <h5>建议更新</h5>
                      <div class="diff-field">
                        <strong>标题：</strong>{{ item.suggested_case.title }}
                      </div>
                      <div class="diff-field">
                        <strong>模块：</strong>{{ item.suggested_case.module }}
                      </div>
                      <div class="diff-field">
                        <strong>前置条件：</strong>{{ item.suggested_case.precondition }}
                      </div>
                      <div class="diff-field">
                        <strong>预期结果：</strong>{{ item.suggested_case.expected_result }}
                      </div>
                    </div>
                  </div>
                  <div v-if="item.diff_fields" class="diff-fields-detail">
                    <el-tag
                      v-for="(_, field) in item.diff_fields"
                      :key="field"
                      size="small"
                      type="warning"
                      class="diff-field-tag"
                      >{{ field }} 已变更</el-tag
                    >
                  </div>
                </template>
                <template v-else>
                  <el-descriptions
                    v-if="item.suggested_case"
                    :column="2"
                    size="small"
                    class="case-detail"
                  >
                    <el-descriptions-item label="模块">{{
                      item.suggested_case.module || '-'
                    }}</el-descriptions-item>
                    <el-descriptions-item label="优先级">{{
                      priorityLabel(item.suggested_case.priority)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="前置条件" :span="2">{{
                      item.suggested_case.precondition || '无'
                    }}</el-descriptions-item>
                    <el-descriptions-item label="预期结果" :span="2">{{
                      item.suggested_case.expected_result
                    }}</el-descriptions-item>
                  </el-descriptions>
                  <el-descriptions
                    v-else-if="item.history_case"
                    :column="2"
                    size="small"
                    class="case-detail"
                  >
                    <el-descriptions-item label="模块">{{
                      item.history_case.module || '-'
                    }}</el-descriptions-item>
                    <el-descriptions-item label="优先级">{{
                      priorityLabel(item.history_case.priority)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="前置条件" :span="2">{{
                      item.history_case.precondition || '无'
                    }}</el-descriptions-item>
                    <el-descriptions-item label="预期结果" :span="2">{{
                      item.history_case.expected_result
                    }}</el-descriptions-item>
                  </el-descriptions>
                </template>
              </el-card>
            </div>
          </template>

          <!-- 普通用例列表（Task9: > 50 条启用虚拟滚动） -->
          <template v-else>
            <div class="preview-list-header">
              共 {{ filteredPreviewCases.length }} 条用例{{ qualityFilter ? `（已过滤）` : '' }}
            </div>
            <div
              v-if="filteredPreviewCases.length > VIRTUAL_THRESHOLD"
              ref="virtualScrollRef"
              class="preview-list-virtual"
              @scroll="handleVirtualScroll"
            >
              <div
                :style="{
                  height: `${filteredPreviewCases.length * ITEM_HEIGHT}px`,
                  position: 'relative',
                }"
              >
                <div
                  v-for="c in visibleCases"
                  :key="c.client_id"
                  class="preview-case-card virtual-item"
                  :class="`quality-${c.quality_status}`"
                  :style="{
                    transform: `translateY(${visibleStartIndex * ITEM_HEIGHT}px)`,
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                  }"
                >
                  <PreviewCaseItem
                    :c="c"
                    @edit="openEditDialog"
                    @regenerate="handleRegenerateSingle"
                    @remove="store.removeCase"
                    @toggle-select="store.recalcQualitySummary"
                  />
                </div>
              </div>
            </div>
            <div v-else class="preview-list">
              <el-card
                v-for="c in filteredPreviewCases"
                :key="c.client_id"
                class="preview-case-card"
                :class="`quality-${c.quality_status}`"
              >
                <PreviewCaseItem
                  :c="c"
                  @edit="openEditDialog"
                  @regenerate="handleRegenerateSingle"
                  @remove="store.removeCase"
                  @toggle-select="store.recalcQualitySummary"
                />
              </el-card>
            </div>
          </template>

          <div class="step-actions">
            <el-button @click="handleRegenerate">返回重新生成</el-button>
            <el-button type="primary" :loading="store.saving" @click="handleSave">保存</el-button>
          </div>
        </template>
      </div>
    </div>

    <SmartGenerateDialogs
      v-model:editVisible="editDialogVisible"
      v-model:saveResultVisible="saveResultDialogVisible"
      v-model:systemCaseVisible="systemCaseSelectDialogVisible"
      :editing-case="editingCase"
      :editing-client-id="editingClientId"
      :save-mode="saveMode"
      @save="handleSave"
      @reset="handleReset"
      @go-to-case-list="goToCaseList"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, WarningFilled, Loading, Upload, Picture, MagicStick, Document, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSmartGenerationStore } from '@/store/smartGeneration'
import type { QualityStatus, SmartPreviewCase } from '@/store/smartGeneration'
import type { HistoryClassificationItem, HistoryClassification } from '@/api/historyAsset'
import { extractErrorDetail } from '@/store/smartGenerationHelpers'
import request from '@/utils/request'
import ErrorState from './components/ErrorState.vue'
import QualityDonutChart from './components/QualityDonutChart.vue'
import PreviewCaseItem from './components/PreviewCaseItem.vue'
import SmartGenerateDialogs from './components/SmartGenerateDialogs.vue'

const router = useRouter()
const route = useRoute()
const store = useSmartGenerationStore()

const projects = ref<{ id: number; name: string }[]>([])
const requirementFiles = ref<{ id: number; file_name: string; original_name: string }[]>([])
const testPoints = ref<{ id: number; name: string; test_point: string; module: string }[]>([])
const saveMode = ref<'draft' | 'formal' | 'passed_only'>('draft')
const systemCaseSelectDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingCase = ref<SmartPreviewCase | null>(null)
const editingClientId = ref<string>('')

// Task2: 4 步流程状态索引
const stepIndex = computed(() => {
  const map: Record<string, number> = { task: 0, material: 1, generating: 2, preview: 3 }
  return map[store.currentStep] ?? 0
})

const contextLoading = ref(false)
const contextError = ref<string>('')
const generationFailed = ref(false)
const saveResultDialogVisible = ref(false)

interface HistoryClassificationItemExt extends HistoryClassificationItem {
  _selectedForSave: boolean
}

function getDefaultSelection(c: HistoryClassification): boolean {
  return c === 'NEW_CASE'
}

function onHistoryItemSelectChange(item: HistoryClassificationItemExt) {
  store.setHistoryItemSelection(item.client_id, item._selectedForSave)
}

const historyClassificationItems = computed<HistoryClassificationItemExt[]>(() => {
  if (!store.historyClassification) return []
  return store.historyClassification.items.map((item) => ({
    ...item,
    _selectedForSave:
      store.historyItemSelections.get(item.client_id) ?? getDefaultSelection(item.classification),
  }))
})

const historyClassificationGroups = computed(() => {
  const groups: {
    key: string
    label: string
    tagType: 'success' | 'warning' | 'primary' | 'danger' | 'info'
    actionHint: string
    items: HistoryClassificationItemExt[]
  }[] = [
    {
      key: 'REUSE_CASE',
      label: '可复用',
      tagType: 'success',
      actionHint: '默认折叠不改',
      items: [],
    },
    {
      key: 'UPDATE_CASE',
      label: '建议修改',
      tagType: 'warning',
      actionHint: '默认待确认',
      items: [],
    },
    {
      key: 'NEW_CASE',
      label: '新增',
      tagType: 'primary',
      actionHint: '默认选中保存草稿',
      items: [],
    },
    {
      key: 'DEPRECATED_CASE',
      label: '可能废弃',
      tagType: 'danger',
      actionHint: '默认不处理',
      items: [],
    },
    {
      key: 'CONFIRM_REQUIRED',
      label: '待确认',
      tagType: 'info',
      actionHint: '默认不保存',
      items: [],
    },
  ]
  for (const item of historyClassificationItems.value) {
    const group = groups.find((g) => g.key === item.classification)
    if (group) group.items.push(item)
  }
  return groups.filter((g) => g.items.length > 0)
})

const unparsedScreenIds = computed(() =>
  store.uiScreenDetails
    .filter((s) => s.parse_status === 'pending' || s.parse_status === 'failed')
    .map((s) => s.id)
)

const canAnalyzeContext = computed(() => {
  if (!store.selectedProjectId) return false
  return store.selectedTask === 'history_update'
    ? store.selectedHistoryAssetIds.length > 0
    : store.testPointIds.length > 0
})

const materialLevelType = computed(() => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | undefined> = {
    L3: 'success',
    L2: undefined,
    L1: 'warning',
    L0: 'danger',
  }
  return map[store.materialLevel] ?? 'info'
})

function qualityTagType(s: QualityStatus): 'success' | 'warning' | 'info' | 'danger' {
  return (
    (
      { passed: 'success', warning: 'warning', pending_review: 'info', rejected: 'danger' } as const
    )[s] || 'info'
  )
}
function qualityLabel(s: QualityStatus) {
  return (
    (
      {
        passed: '通过',
        warning: '有轻微问题',
        pending_review: '需要确认',
        rejected: '不建议保存',
      } as const
    )[s] || s
  )
}
function priorityLabel(p: number) {
  return ({ 1: '高', 2: '中', 3: '低' } as const)[p] || '中'
}
function parseStatusLabel(s: string | undefined) {
  return (
    ({ completed: '已解析', pending: '待解析', running: '解析中', failed: '解析失败' } as const)[
      s || 'pending'
    ] || '待解析'
  )
}
function confidenceLabel(c: string) {
  return (
    (
      {
        explicit: '精确匹配',
        ui_file: 'UI文件匹配',
        matched: '关键词匹配',
        adjacent: '相邻页面',
      } as const
    )[c] || c
  )
}
function assetTypeLabel(t: string) {
  return ({ excel: 'Excel', xmind: 'XMind', system_cases: '系统用例' } as const)[t] || t
}
function historyParseStatusLabel(s: string) {
  return (
    ({ completed: '已解析', pending: '待解析', parsing: '解析中', failed: '解析失败' } as const)[
      s
    ] || '待解析'
  )
}

// 暴露给子组件使用
void qualityTagType

function extractListData(resp: unknown) {
  const data = (resp as { data?: unknown })?.data || resp
  return Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
}

async function loadProjects() {
  try {
    projects.value = extractListData(
      await request.get('/api/v1/project/list?page=1&page_size=100')
    ) as { id: number; name: string }[]
  } catch {
    projects.value = []
  }
}
async function loadProjectFiles() {
  if (!store.selectedProjectId) {
    requirementFiles.value = []
    return
  }
  try {
    requirementFiles.value = extractListData(
      await request.get(
        `/api/v1/file/list?project_id=${store.selectedProjectId}&resource_type=requirement`
      )
    ) as { id: number; file_name: string; original_name: string }[]
  } catch {
    requirementFiles.value = []
  }
}
async function loadTestPoints() {
  if (!store.selectedProjectId) {
    testPoints.value = []
    return
  }
  try {
    testPoints.value = extractListData(
      await request.get(`/api/v1/test-point/list/${store.selectedProjectId}?page=1&page_size=100`)
    ) as { id: number; name: string; test_point: string; module: string }[]
  } catch {
    testPoints.value = []
  }
}

watch(
  () => store.selectedProjectId,
  async (val) => {
    if (val) {
      await Promise.all([
        loadProjectFiles(),
        loadTestPoints(),
        store.loadUIPrototypeProjects(),
        store.loadHistoryAssets(),
      ])
    } else {
      requirementFiles.value = []
      testPoints.value = []
    }
  }
)

// Task2: 点卡片即确认 task，不再分离"进入生成"动作
function selectTask(task: 'new_feature' | 'history_update') {
  store.selectedTask = task
  store.currentStep = 'material'
}
function goToTestPointManagement() {
  router.push({ name: 'TestPointManagement' })
}
function goToCaseList() {
  router.push({ name: 'CaseList' })
}

function toggleHistoryAsset(assetId: number) {
  const idx = store.selectedHistoryAssetIds.indexOf(assetId)
  idx >= 0
    ? store.selectedHistoryAssetIds.splice(idx, 1)
    : store.selectedHistoryAssetIds.push(assetId)
}

async function handleHistoryAssetFileChange(uploadFile: unknown) {
  const raw = (uploadFile as { raw: File }).raw
  if (!raw || !store.selectedProjectId) return
  try {
    await store.uploadHistoryAsset(
      raw,
      raw.name.toLowerCase().endsWith('.xmind') ? 'xmind' : 'excel'
    )
    ElMessage.success('历史资产上传成功')
  } catch (e: unknown) {
    // Task8.1: 透出真实原因，兜底才用通用文案
    ElMessage.error(extractErrorDetail(e, '上传失败'))
  }
}

async function handleAnalyzeContext() {
  if (!canAnalyzeContext.value) {
    ElMessage.warning(
      store.selectedTask === 'history_update'
        ? '请选择项目和至少一个历史资产'
        : '请选择项目和至少一个测试点'
    )
    return
  }
  contextLoading.value = true
  contextError.value = ''
  try {
    await store.createBatch()
    if (store.selectedTask === 'history_update') await store.alignHistoryAssets()
    await store.fetchContext()
  } catch (e: unknown) {
    // Task8.1: 透出后端 detail，兜底才用通用文案
    contextError.value = extractErrorDetail(e, '资料识别失败')
  } finally {
    contextLoading.value = false
  }
}

async function handleStartGeneration() {
  generationFailed.value = false
  store.currentStep = 'generating'
  await store.startGeneration()
  // 仅在生成结束且有失败信号时标记失败（取消不算失败）
  if (
    !store.generating &&
    store.previewCases.length === 0 &&
    store.generationProgress &&
    store.generationProgress !== '已取消生成'
  ) {
    generationFailed.value = true
  }
  if (store.previewCases.length > 0) store.currentStep = 'preview'
}

// Task4.2: 取消按钮调用 store.abortGeneration() 真中断，而非仅置 generating=false
function handleCancelGeneration() {
  store.abortGeneration()
}

async function handleRetryGeneration() {
  generationFailed.value = false
  store.generationProgress = ''
  store.currentStep = 'generating'
  await store.startGeneration()
  if (
    !store.generating &&
    store.previewCases.length === 0 &&
    store.generationProgress &&
    store.generationProgress !== '已取消生成'
  ) {
    generationFailed.value = true
  }
  if (store.previewCases.length > 0) store.currentStep = 'preview'
}

function handleRegenerate() {
  store.previewCases = []
  qualityFilter.value = null
  store.currentStep = 'material'
}

async function handleRegenerateSingle(clientId: string) {
  try {
    await store.regenerateSingleCase(clientId)
    ElMessage.success('重新生成完成')
  } catch (e: unknown) {
    // Task8.1: 透出真实原因
    ElMessage.error(extractErrorDetail(e, '重新生成失败'))
  }
}

const isAllSelected = computed(
  () => store.previewCases.length > 0 && store.previewCases.every((c) => c.selected_for_save)
)
const isIndeterminate = computed(() => {
  const selected = store.previewCases.filter((c) => c.selected_for_save).length
  return selected > 0 && selected < store.previewCases.length
})
const selectedCaseCount = computed(
  () => store.previewCases.filter((c) => c.selected_for_save).length
)

function handleToggleAll(val: boolean | string | number) {
  const checked = Boolean(val)
  for (const c of store.previewCases) c.selected_for_save = checked
  store.recalcQualitySummary()
}

async function handleBatchDelete() {
  const selectedIds = store.previewCases.filter((c) => c.selected_for_save).map((c) => c.client_id)
  if (selectedIds.length === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.length} 条用例？`, '批量删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    for (const id of selectedIds) store.removeCase(id)
    ElMessage.success(`已删除 ${selectedIds.length} 条用例`)
  } catch {
    /* 用户取消 */
  }
}

const batchRegenerating = ref(false)

// Task5: 手写信号量，并发上限 3，不引入 p-limit 新依赖
const MAX_CONCURRENCY = 3
async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  fn: (item: T, index: number) => Promise<void>
): Promise<void> {
  let cursor = 0
  const workers: Promise<void>[] = []
  const worker = async () => {
    while (cursor < items.length) {
      const idx = cursor++
      await fn(items[idx], idx)
    }
  }
  for (let i = 0; i < Math.min(limit, items.length); i++) workers.push(worker())
  await Promise.all(workers)
}

// Task5: 批量重生成并发化（Promise.all + 并发上限 3）
// 注：单条独立 AbortController 受限于 store 单 controller 设计；
//   并发期间"取消重生成"按钮调用 store.abortGeneration() 中断最近开始的一条
async function handleBatchRegenerate() {
  const selectedCases = store.previewCases.filter((c) => c.selected_for_save)
  if (selectedCases.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定重新生成选中的 ${selectedCases.length} 条用例？`,
      '批量重新生成',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  batchRegenerating.value = true
  let successCount = 0
  let failCount = 0
  await runWithConcurrency(selectedCases, MAX_CONCURRENCY, async (c) => {
    try {
      await store.regenerateSingleCase(c.client_id)
      successCount++
    } catch {
      failCount++
    }
  })
  batchRegenerating.value = false
  if (failCount > 0)
    ElMessage.warning(`重新生成完成：成功 ${successCount} 条，失败 ${failCount} 条`)
  else ElMessage.success(`已重新生成 ${successCount} 条用例`)
}

function handleCancelBatchRegenerate() {
  store.abortGeneration()
}

// Task11: 质量分布过滤
const qualityFilter = ref<QualityStatus | null>(null)
function handleQualityFilter(status: QualityStatus | null) {
  qualityFilter.value = status
}
const filteredPreviewCases = computed(() => {
  if (!qualityFilter.value) return store.previewCases
  return store.previewCases.filter((c) => c.quality_status === qualityFilter.value)
})

// Task9: 虚拟滚动（> 50 条启用）
const VIRTUAL_THRESHOLD = 50
const ITEM_HEIGHT = 240
const VISIBLE_BUFFER = 5
const virtualScrollRef = ref<HTMLElement | null>(null)
const visibleStartIndex = ref(0)
const visibleEndIndex = ref(Math.min(20, filteredPreviewCases.value.length))

const visibleCases = computed(() =>
  filteredPreviewCases.value.slice(visibleStartIndex.value, visibleEndIndex.value)
)

function handleVirtualScroll() {
  const el = virtualScrollRef.value
  if (!el) return
  const scrollTop = el.scrollTop
  const viewportHeight = el.clientHeight
  const start = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - VISIBLE_BUFFER)
  const visibleCount = Math.ceil(viewportHeight / ITEM_HEIGHT) + VISIBLE_BUFFER * 2
  visibleStartIndex.value = start
  visibleEndIndex.value = Math.min(filteredPreviewCases.value.length, start + visibleCount)
}

watch(
  () => filteredPreviewCases.value.length,
  () => {
    visibleStartIndex.value = 0
    visibleEndIndex.value = Math.min(20, filteredPreviewCases.value.length)
    handleVirtualScroll()
  }
)

function openEditDialog(c: SmartPreviewCase) {
  editingClientId.value = c.client_id
  editingCase.value = JSON.parse(JSON.stringify(c))
  editDialogVisible.value = true
}

async function handleSave() {
  if (saveMode.value === 'formal') {
    try {
      await ElMessageBox.confirm(
        '当前结果由 AI 生成，建议先保存为草稿并人工复核。确定要保存为正式用例吗？',
        '保存确认',
        { confirmButtonText: '确定保存', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }
  await store.saveBatch(saveMode.value)
  // Task2: 保存结果用弹窗展示（合并 save_result 步骤）
  if (store.saveResult || store.saveError) saveResultDialogVisible.value = true
}

function handleReset() {
  store.reset()
  saveMode.value = 'draft'
  qualityFilter.value = null
  saveResultDialogVisible.value = false
  generationFailed.value = false
  contextError.value = ''
}
function handleBack() {
  router.back()
}

// Task10.3: onMounted 恢复用户偏好 + 兼容 ai-generate 跳转的 query 参数
onMounted(async () => {
  await loadProjects()
  store.restorePreference()

  const qid = route.query.project_id
  if (qid) {
    const pid = Number(qid)
    if (!Number.isNaN(pid) && pid > 0) {
      store.selectedProjectId = pid
      store.selectedTask = 'new_feature'
      store.currentStep = 'material'
      await Promise.all([loadProjectFiles(), loadTestPoints(), store.loadUIPrototypeProjects()])

      const tpIds = route.query.test_point_ids
      if (tpIds) {
        try {
          const parsed = JSON.parse(String(tpIds))
          if (Array.isArray(parsed)) {
            store.testPointIds = parsed.map(Number).filter((n: number) => !Number.isNaN(n) && n > 0)
          }
        } catch {
          /* ignore */
        }
      }

      const uiProjectId = Number(route.query.ui_project_id || 0)
      if (uiProjectId > 0) {
        store.selectedUIPrototypeProjectId = uiProjectId
        await store.handleUIPrototypeProjectChange(uiProjectId)
      }
    }
  }

  window.addEventListener('keydown', handleKeydown)
})
onBeforeUnmount(() => {
  store.cancelParsePolling()
  window.removeEventListener('keydown', handleKeydown)
})

// Task13: 键盘快捷键（Ctrl+S/Esc/Ctrl+A，仅在对应步骤生效）
function handleKeydown(event: KeyboardEvent) {
  const isMod = event.ctrlKey || event.metaKey
  // Ctrl/Cmd+S（预览页）触发保存
  if (isMod && event.key.toLowerCase() === 's') {
    if (store.currentStep !== 'preview' || store.saving) return
    event.preventDefault()
    handleSave()
    return
  }
  // Ctrl/Cmd+A（预览页）触发全选
  if (isMod && event.key.toLowerCase() === 'a') {
    if (store.currentStep !== 'preview') return
    if (store.selectedTask === 'history_update') return
    event.preventDefault()
    handleToggleAll(!isAllSelected.value)
    return
  }
  // Esc：弹窗打开关闭弹窗；生成中取消生成
  if (event.key === 'Escape') {
    if (editDialogVisible.value) {
      editDialogVisible.value = false
      return
    }
    if (store.uiUploadDialogVisible) {
      store.uiUploadDialogVisible = false
      return
    }
    if (systemCaseSelectDialogVisible.value) {
      systemCaseSelectDialogVisible.value = false
      return
    }
    if (saveResultDialogVisible.value) {
      saveResultDialogVisible.value = false
      return
    }
    if (store.currentStep === 'generating' && store.generating) {
      store.abortGeneration()
    }
  }
}
</script>

<style scoped>
.smart-generate-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
}
.steps-indicator {
  margin-bottom: 32px;
}
.step-content {
  min-height: 400px;
}
.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
}
.task-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.task-card {
  border: 2px solid var(--color-border);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fff;
}
.task-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}
.task-card.active {
  border-color: var(--color-primary);
  background: #ecf5ff;
}
.task-card.primary {
  border-color: var(--color-primary);
}
.task-card.disabled {
  opacity: 0.7;
}
.task-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.task-card h3 {
  margin: 0 0 8px;
  font-size: 18px;
}
.task-card p {
  color: var(--color-info);
  margin: 0 0 16px;
  font-size: 14px;
}
.task-tags {
  margin-bottom: 16px;
}
.task-tags .el-tag {
  margin: 0 4px;
}
.task-btn-hint {
  color: var(--color-primary);
  font-size: 13px;
  margin-top: 8px;
}
.task-btn {
  width: 100%;
}
.material-form {
  max-width: 600px;
}
.empty-block {
  margin-top: 8px;
}
.optional-hint {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 4px;
}
.ui-project-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.ui-screen-section {
  margin-top: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
}
.ui-screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.ui-screen-header h4 {
  margin: 0;
}
.ui-screen-actions {
  display: flex;
  gap: 8px;
}
.ui-parse-alert {
  margin-bottom: 12px;
}
.ui-screen-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.ui-screen-card {
  border: 2px solid var(--color-border);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.ui-screen-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}
.ui-screen-card.selected {
  border-color: var(--color-primary);
  background: #ecf5ff;
}
.ui-screen-card.parse-failed {
  border-color: var(--color-danger);
  opacity: 0.8;
}
.ui-screen-card.parse-pending {
  border-color: var(--color-warning);
  opacity: 0.85;
}
.screen-thumb {
  width: 100%;
  height: 80px;
  overflow: hidden;
  border-radius: 4px;
  background: var(--color-bg-page);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
}
.screen-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.screen-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  margin-bottom: 4px;
}
.screen-name {
  font-size: 12px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  text-align: left;
}
.screen-elements {
  font-size: 11px;
  color: var(--color-info);
}
.screen-error {
  font-size: 11px;
  color: var(--color-danger);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.advanced-collapse {
  max-width: 600px;
  margin-top: 16px;
}
.context-card,
.warning-card,
.evidence-card,
.strategy-card,
.classification-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.warning-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
}
.evidence-group {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  flex-wrap: wrap;
}
.evidence-item {
  font-size: 13px;
  color: var(--color-text-regular);
  padding: 2px 6px;
  background: var(--color-bg-page);
  border-radius: 4px;
}
.progress-content {
  text-align: center;
  padding: 40px 0;
}
.spin-icon {
  animation: spin 1.5s linear infinite;
  margin-bottom: 16px;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
.progress-hint {
  color: var(--color-info);
  margin-top: 12px;
}
.preview-skeleton {
  margin-top: 24px;
  text-align: left;
}
.preview-summary-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
.preview-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: var(--color-bg-page);
  border-radius: 6px;
  flex-wrap: wrap;
}
.coverage-collapse {
  margin-bottom: 16px;
}
.coverage-tag {
  margin: 2px 4px;
}
.save-confirm-card {
  margin-bottom: 16px;
}
.save-alert {
  margin-bottom: 16px;
}
.save-mode-select {
  margin-top: 16px;
}
.save-mode-select h4 {
  margin: 0 0 12px;
}
.save-warning {
  color: var(--color-warning);
  font-size: 13px;
  margin-top: 8px;
}
.preview-list-header {
  color: var(--color-text-regular);
  font-size: 13px;
  margin-bottom: 8px;
}
.preview-case-card {
  margin-bottom: 12px;
  border-left: 4px solid var(--color-border);
}
.preview-case-card.quality-passed {
  border-left-color: var(--color-success);
}
.preview-case-card.quality-warning {
  border-left-color: var(--color-warning);
}
.preview-case-card.quality-pending_review {
  border-left-color: var(--color-primary);
}
.preview-case-card.quality-rejected {
  border-left-color: var(--color-danger);
}
.preview-case-card.classification-REUSE_CASE {
  border-left-color: var(--color-success);
}
.preview-case-card.classification-UPDATE_CASE {
  border-left-color: var(--color-warning);
}
.preview-case-card.classification-NEW_CASE {
  border-left-color: var(--color-primary);
}
.preview-case-card.classification-DEPRECATED_CASE {
  border-left-color: var(--color-danger);
}
.preview-case-card.classification-CONFIRM_REQUIRED {
  border-left-color: var(--color-info);
}
.preview-list-virtual {
  max-height: 70vh;
  overflow-y: auto;
  position: relative;
}
.virtual-item {
  will-change: transform;
}
.history-asset-section {
  width: 100%;
}
.history-upload-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.history-asset-list {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 8px;
}
.history-asset-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.history-asset-item:last-child {
  border-bottom: none;
}
.asset-filename {
  flex: 1;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.classification-summary {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.classification-total {
  color: var(--color-info);
  font-size: 13px;
}
.classification-group {
  margin-bottom: 20px;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--color-bg-page);
}
.group-header.group-REUSE_CASE {
  border-left: 4px solid var(--color-success);
}
.group-header.group-UPDATE_CASE {
  border-left: 4px solid var(--color-warning);
}
.group-header.group-NEW_CASE {
  border-left: 4px solid var(--color-primary);
}
.group-header.group-DEPRECATED_CASE {
  border-left: 4px solid var(--color-danger);
}
.group-header.group-CONFIRM_REQUIRED {
  border-left: 4px solid var(--color-info);
}
.group-action-hint {
  color: var(--color-info);
  font-size: 13px;
}
.confidence-hint {
  font-size: 12px;
  color: var(--color-warning);
}
.classification-reason {
  font-size: 12px;
  color: var(--color-info);
  margin-left: auto;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.diff-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 8px;
}
.diff-side {
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
}
.diff-side h5 {
  margin: 0 0 8px;
  font-size: 14px;
}
.diff-old {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}
.diff-old h5 {
  color: var(--color-danger);
}
.diff-new {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
}
.diff-new h5 {
  color: var(--color-success);
}
.diff-field {
  margin-bottom: 4px;
  line-height: 1.6;
}
.diff-fields-detail {
  margin-top: 8px;
}
.diff-field-tag {
  margin: 2px 4px;
}
</style>
