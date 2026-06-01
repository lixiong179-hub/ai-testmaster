<template>
  <div class="smart-generate-container">
    <div class="page-header">
      <h2>智能生成用例</h2>
      <el-button @click="handleBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <el-steps :active="stepIndex" finish-status="success" class="steps-indicator" align-center>
      <el-step title="选择任务" />
      <el-step title="选择资料" />
      <el-step title="资料识别" />
      <el-step title="策略确认" />
      <el-step title="生成用例" />
      <el-step title="预览结果" />
      <el-step title="保存确认" />
      <el-step title="保存结果" />
    </el-steps>

    <div class="step-content">
      <!-- Step 1: 任务选择 -->
      <div v-if="store.currentStep === 'task'" class="task-select">
        <div class="task-cards">
          <div
            class="task-card primary"
            :class="{ active: store.selectedTask === 'new_feature' }"
            @click="store.selectedTask = 'new_feature'"
          >
            <div class="task-icon">🚀</div>
            <h3>新功能生成用例</h3>
            <p>我有新需求或测试点，要生成测试用例</p>
            <div class="task-tags">
              <el-tag size="small">需求文档</el-tag>
              <el-tag size="small">测试点</el-tag>
              <el-tag size="small" type="info">UI原型（可选）</el-tag>
            </div>
            <el-button type="primary" class="task-btn" @click="goToMaterial">进入生成</el-button>
          </div>
          <div class="task-card disabled">
            <div class="task-icon">📋</div>
            <h3>历史资产更新用例</h3>
            <p>我有旧用例，要基于新版本更新</p>
            <div class="task-tags">
              <el-tag size="small" type="info">Excel</el-tag>
              <el-tag size="small" type="info">XMind</el-tag>
              <el-tag size="small" type="info">保鲜建议</el-tag>
            </div>
            <el-button class="task-btn" @click="goToCaseMigration">前往用例迁移</el-button>
          </div>
          <div class="task-card disabled">
            <div class="task-icon">📥</div>
            <h3>导入测试资产</h3>
            <p>我只想先把旧资产导入系统</p>
            <div class="task-tags">
              <el-tag size="small" type="info">Excel</el-tag>
              <el-tag size="small" type="info">XMind</el-tag>
            </div>
            <el-button class="task-btn" @click="goToTestPointManagement">前往测试点管理</el-button>
          </div>
        </div>
      </div>

      <!-- Step 2: 资料选择 -->
      <div v-else-if="store.currentStep === 'material'" class="material-select">
        <el-form label-width="100px" class="material-form">
          <el-form-item label="项目" required>
            <el-select v-model="store.selectedProjectId" placeholder="选择项目" filterable style="width: 100%">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求文件">
            <el-select v-model="store.requirementFileIds" multiple placeholder="选择需求文件（可选）" filterable style="width: 100%">
              <el-option v-for="f in requirementFiles" :key="f.id" :label="f.file_name || f.original_name" :value="f.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="测试点" required>
            <el-select v-model="store.testPointIds" multiple placeholder="选择测试点" filterable style="width: 100%">
              <el-option v-for="tp in testPoints" :key="tp.id" :label="`${tp.module || ''} - ${tp.name || tp.test_point || ''}`" :value="tp.id" />
            </el-select>
            <div v-if="testPoints.length === 0 && store.selectedProjectId" class="empty-hint">
              暂无测试点，请先前往
              <el-link type="primary" @click="goToTestPointManagement">测试点管理</el-link>
              提取或新建
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
                <el-option v-for="p in store.uiPrototypeProjects" :key="p.id" :label="p.name" :value="p.id">
                  <span>{{ p.name }}</span>
                  <el-tag size="small" type="info" style="margin-left: 8px">{{ p.screen_count || 0 }} 页</el-tag>
                </el-option>
              </el-select>
              <el-button size="default" @click="store.uiUploadDialogVisible = true">
                <el-icon><Upload /></el-icon>
                上传UI页面
              </el-button>
            </div>
            <div class="optional-hint">UI原型图可选，不提供也能继续生成。可直接上传截图，无需先创建原型项目</div>
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
                :loading="store.uiParsing"
                @click="store.parseUIScreens(unparsedScreenIds)"
              >
                解析待处理页面 ({{ unparsedScreenIds.length }})
              </el-button>
            </div>
          </div>

          <el-alert v-if="store.hasUIParseFailure" type="warning" :closable="false" show-icon class="ui-parse-alert">
            <template #title>部分 UI 页面解析失败，不影响生成，但相关步骤需人工确认页面元素</template>
          </el-alert>

          <el-alert v-if="store.hasUIParsePending" type="info" :closable="false" show-icon class="ui-parse-alert">
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
                'parse-pending': screen.parse_status === 'pending' || screen.parse_status === 'running',
              }"
              @click="store.toggleUIScreen(screen.id)"
            >
              <div class="screen-thumb">
                <img v-if="store.uiScreenImageUrls[screen.id]" :src="store.uiScreenImageUrls[screen.id]" :alt="screen.screen_name" />
                <el-icon v-else :size="32" color="#c0c4cc"><Picture /></el-icon>
              </div>
              <div class="screen-info">
                <span class="screen-name">{{ screen.screen_name || `页面${screen.id}` }}</span>
                <el-tag
                  size="small"
                  :type="screen.parse_status === 'completed' ? 'success' : screen.parse_status === 'failed' ? 'danger' : 'info'"
                >
                  {{ parseStatusLabel(screen.parse_status) }}
                </el-tag>
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
              <el-form-item label="用例类型">
                <el-select v-model="store.advancedConfig.case_type">
                  <el-option label="手工用例" value="manual" />
                  <el-option label="UI自动化" value="ui_automation" />
                  <el-option label="API自动化" value="api_automation" />
                </el-select>
              </el-form-item>
              <el-form-item label="执行模式">
                <el-select v-model="store.advancedConfig.exec_mode">
                  <el-option label="手工执行" value="manual" />
                  <el-option label="全部" value="all" />
                </el-select>
              </el-form-item>
              <el-form-item label="默认优先级">
                <el-select v-model="store.advancedConfig.priority">
                  <el-option label="高" :value="1" />
                  <el-option label="中" :value="2" />
                  <el-option label="低" :value="3" />
                </el-select>
              </el-form-item>
              <el-form-item label="生成模式">
                <el-select v-model="store.advancedConfig.mode">
                  <el-option label="线性模式" value="linear" />
                  <el-option label="图谱模式" value="graph" />
                </el-select>
              </el-form-item>
            </el-form>
          </el-collapse-item>
        </el-collapse>

        <div class="step-actions">
          <el-button @click="store.currentStep = 'task'">返回</el-button>
          <el-button type="primary" :disabled="!canAnalyzeContext" @click="handleAnalyzeContext">分析资料</el-button>
        </div>
      </div>

      <!-- Step 3: 资料识别 -->
      <div v-else-if="store.currentStep === 'context'" class="context-result">
        <el-card class="context-card">
          <template #header>
            <div class="card-header">
              <span>资料识别结果</span>
              <el-tag :type="materialLevelType">{{ store.materialLevelText }}</el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="需求命中">{{ (store.contextStats.requirements_used as number) || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="测试点数量">{{ (store.contextStats.test_points_loaded as number) || 0 }} 个</el-descriptions-item>
            <el-descriptions-item label="UI页面命中">{{ (store.contextStats.ui_screens_used as number) || 0 }} 页</el-descriptions-item>
            <el-descriptions-item label="历史参考">{{ (store.contextStats.history_cases_used as number) || 0 }} 条</el-descriptions-item>
            <el-descriptions-item label="完整度评分">
              <el-progress :percentage="(store.contextStats.completeness_score as number) || 0" :stroke-width="12" />
            </el-descriptions-item>
            <el-descriptions-item label="低可信过滤">{{ (store.contextStats.history_low_trust_filtered as number) || 0 }} 条</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card v-if="store.evidenceRefsDisplay.length > 0" class="evidence-card">
          <template #header><span>来源依据</span></template>
          <div v-for="ref in store.evidenceRefsDisplay" :key="ref.type" class="evidence-group">
            <el-tag size="small" :type="ref.type === 'requirement' ? undefined : ref.type === 'ui' ? 'success' : 'info'">{{ ref.label }}</el-tag>
            <span v-for="(item, i) in ref.items" :key="i" class="evidence-item">{{ item }}</span>
          </div>
        </el-card>

        <el-card v-if="store.uiScreenMatchResults.length > 0" class="ui-match-card">
          <template #header><span>UI 页面匹配结果</span></template>
          <el-table :data="store.uiScreenMatchResults" size="small" stripe>
            <el-table-column prop="screen_name" label="页面名称" />
            <el-table-column prop="confidence" label="匹配置信度" width="140">
              <template #default="{ row }">
                <el-tag size="small" :type="row.confidence === 'explicit' ? 'success' : row.confidence === 'matched' ? 'primary' : 'info'">
                  {{ confidenceLabel(row.confidence) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="element_count" label="识别元素" width="100" />
          </el-table>
        </el-card>

        <el-card v-if="store.warnings.length > 0" class="warning-card">
          <template #header><span>风险提示</span></template>
          <div v-for="w in store.warningUserTexts" :key="w.code" class="warning-item">
            <el-icon color="#E6A23C"><WarningFilled /></el-icon>
            <span>{{ w.text }}</span>
          </div>
        </el-card>

        <div class="step-actions">
          <el-button @click="store.currentStep = 'material'">返回修改资料</el-button>
          <el-button type="primary" @click="goToStrategy">查看推荐策略</el-button>
        </div>
      </div>

      <!-- Step 4: 策略确认 -->
      <div v-else-if="store.currentStep === 'strategy'" class="strategy-confirm">
        <el-card>
          <template #header><span>推荐生成策略</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="策略">{{ store.strategyDisplayText }}</el-descriptions-item>
            <el-descriptions-item label="依据">
              {{ store.scenarioType === 'A1_REQUIREMENT_TESTPOINT_UI' ? '需求 + 测试点 + UI' : '需求 + 测试点' }}
            </el-descriptions-item>
            <el-descriptions-item label="重点">
              {{ store.scenarioType === 'A1_REQUIREMENT_TESTPOINT_UI' ? '功能、异常、边界、页面交互、元素校验' : '功能、异常、边界、权限、状态、数据校验' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="store.uiScreenIds.length === 0" label="风险">
              <el-text type="warning">UI 元素和页面布局需要人工确认</el-text>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
        <div class="step-actions">
          <el-button @click="store.currentStep = 'context'">返回修改资料</el-button>
          <el-button type="primary" size="large" @click="handleStartGeneration">开始生成</el-button>
        </div>
      </div>

      <!-- Step 5: 生成进度 / 失败恢复 -->
      <div v-else-if="store.currentStep === 'generating'" class="generating-progress">
        <el-card v-if="store.generating || !store.generationProgress">
          <div class="progress-content">
            <el-icon class="spin-icon" :size="48" color="#409EFF"><Loading /></el-icon>
            <h3>{{ store.generationProgress || '正在生成...' }}</h3>
            <el-progress :percentage="100" :indeterminate="true" :stroke-width="8" />
            <p class="progress-hint">AI 正在根据您的资料生成测试用例，请耐心等待</p>
          </div>
        </el-card>
        <el-card v-else>
          <el-result icon="error" title="生成未完成" :sub-title="store.generationProgress">
            <template #extra>
              <div class="recovery-actions">
                <el-button type="primary" @click="handleRetryGeneration">重试生成</el-button>
                <el-button @click="store.currentStep = 'material'">返回修改资料</el-button>
                <el-button @click="handleReset">重新开始</el-button>
              </div>
            </template>
          </el-result>
        </el-card>
        <div class="step-actions">
          <el-button v-if="store.generating" @click="handleCancelGeneration">取消生成</el-button>
        </div>
      </div>

      <!-- Step 6: 预览结果 -->
      <div v-else-if="store.currentStep === 'preview'" class="preview-results">
        <div class="preview-summary">
          <el-tag type="success">可直接保存 {{ store.passedCount }} 条</el-tag>
          <el-tag type="warning">需要确认 {{ store.pendingReviewCount + store.warningCount }} 条</el-tag>
          <el-tag type="danger">不建议保存 {{ store.rejectedCount }} 条</el-tag>
        </div>

        <el-collapse class="coverage-collapse">
          <el-collapse-item title="覆盖摘要" name="coverage">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="总用例数">{{ store.coverageSummary.total }}</el-descriptions-item>
              <el-descriptions-item label="分类分布">
                <el-tag v-for="(count, cat) in store.coverageSummary.byCategory" :key="cat as string" size="small" class="coverage-tag">
                  {{ cat }}: {{ count }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="测试点覆盖" :span="2">
                <el-tag v-for="(count, tp) in store.coverageSummary.byTestPoint" :key="tp as string" size="small" type="info" class="coverage-tag">
                  {{ tp }}: {{ count }}条
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>

        <div class="preview-list">
          <el-card v-for="c in store.previewCases" :key="c.client_id" class="preview-case-card" :class="`quality-${c.quality_status}`">
            <div class="case-header">
              <el-checkbox v-model="c.selected_for_save" @change="store.recalcQualitySummary()" />
              <span class="case-title">{{ c.title }}</span>
              <el-tag :type="qualityTagType(c.quality_status)" size="small">{{ qualityLabel(c.quality_status) }}</el-tag>
              <el-tag size="small" type="info">{{ c.case_type }}</el-tag>
              <el-tag v-if="c.dirty" size="small" type="warning">已编辑</el-tag>
              <el-tag v-if="c.regenerating" size="small" type="info">重新生成中...</el-tag>
              <div class="case-actions">
                <el-button size="small" text type="primary" @click="openEditDialog(c)">编辑</el-button>
                <el-button size="small" text type="primary" :loading="c.regenerating" @click="handleRegenerateSingle(c.client_id)">重新生成</el-button>
                <el-button size="small" text type="danger" @click="store.removeCase(c.client_id)">删除</el-button>
              </div>
            </div>
            <el-descriptions :column="2" size="small" class="case-detail">
              <el-descriptions-item label="模块">{{ c.module || '-' }}</el-descriptions-item>
              <el-descriptions-item label="优先级">{{ priorityLabel(c.priority) }}</el-descriptions-item>
              <el-descriptions-item label="前置条件" :span="2">{{ c.precondition || '无' }}</el-descriptions-item>
              <el-descriptions-item label="步骤" :span="2">
                <ol class="step-list">
                  <li v-for="(s, i) in c.steps" :key="i">{{ (s as Record<string, unknown>).action || (s as Record<string, unknown>).step }}</li>
                </ol>
              </el-descriptions-item>
              <el-descriptions-item label="预期结果" :span="2">{{ c.expected_result }}</el-descriptions-item>
              <el-descriptions-item v-if="c.source_refs && Object.keys(c.source_refs).length > 0" label="来源依据" :span="2">
                <span v-if="c.source_refs.ui_screen_name" class="source-ref-item">
                  <el-tag size="small" type="success">UI: {{ c.source_refs.ui_screen_name }}</el-tag>
                </span>
                <span v-if="c.source_refs.requirement_file_name" class="source-ref-item">
                  <el-tag size="small">需求: {{ c.source_refs.requirement_file_name }}</el-tag>
                </span>
                <span v-if="c.source_refs.test_point_name" class="source-ref-item">
                  <el-tag size="small" type="info">测试点: {{ c.source_refs.test_point_name }}</el-tag>
                </span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </div>

        <div class="step-actions">
          <el-button @click="handleRegenerate">返回重新生成</el-button>
          <el-button type="primary" @click="store.currentStep = 'save_confirm'">确认保存</el-button>
        </div>
      </div>

      <!-- Step 7: 保存确认 -->
      <div v-else-if="store.currentStep === 'save_confirm'" class="save-confirm">
        <el-card>
          <template #header><span>保存确认</span></template>
          <el-alert type="warning" :closable="false" show-icon class="save-alert">
            <template #title>当前只是生成预览，尚未入库。点击保存后才会写入用例库。</template>
          </el-alert>
          <el-descriptions :column="1" border class="save-summary">
            <el-descriptions-item label="本次将保存">
              <el-tag type="success">可直接保存 {{ store.passedCount }} 条</el-tag>
              <el-tag type="warning">需要确认 {{ store.warningCount + store.pendingReviewCount }} 条</el-tag>
              <el-tag type="danger">不建议保存 {{ store.rejectedCount }} 条</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="已选中保存">{{ store.selectedForSaveCount }} 条</el-descriptions-item>
          </el-descriptions>
          <div class="save-mode-select">
            <h4>保存方式</h4>
            <el-radio-group v-model="saveMode">
              <el-radio value="draft">保存为草稿（推荐）</el-radio>
              <el-radio value="formal">保存为正式用例</el-radio>
              <el-radio value="passed_only">仅保存已通过项</el-radio>
            </el-radio-group>
            <p v-if="saveMode === 'formal'" class="save-warning">
              当前结果由 AI 生成，建议先保存为草稿并人工复核。如保存为正式用例，请确认步骤、预期结果和来源依据均已核对。
            </p>
          </div>
        </el-card>
        <div class="step-actions">
          <el-button @click="store.currentStep = 'preview'">返回预览</el-button>
          <el-button type="primary" :loading="store.saving" @click="handleSave">保存</el-button>
        </div>
      </div>

      <!-- Step 8: 保存结果 -->
      <div v-else-if="store.currentStep === 'save_result'" class="save-result">
        <el-card v-if="store.saveResult">
          <template #header><span>保存结果</span></template>
          <el-result
            :icon="store.saveResult.status === 'saved' ? 'success' : store.saveResult.status === 'partial_saved' ? 'warning' : 'error'"
            :title="store.saveResult.status === 'saved' ? '保存成功' : store.saveResult.status === 'partial_saved' ? '部分保存成功' : '保存失败'"
          >
            <template #extra>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="成功数量">{{ store.saveResult.saved_count }}</el-descriptions-item>
                <el-descriptions-item label="失败数量">{{ store.saveResult.failed_count }}</el-descriptions-item>
              </el-descriptions>
              <div v-if="store.saveResult.failures.length > 0" class="failure-list">
                <h4>失败明细</h4>
                <div v-for="(f, i) in store.saveResult.failures" :key="i" class="failure-item">
                  <el-tag type="danger" size="small">{{ f.title || f.client_id }}</el-tag>
                  <span>{{ f.reason }}</span>
                </div>
              </div>
              <div class="result-actions">
                <el-button type="primary" @click="goToCaseList">查看已保存用例</el-button>
                <el-button @click="handleReset">重新生成</el-button>
              </div>
            </template>
          </el-result>
        </el-card>
        <el-card v-else-if="store.saveError">
          <el-result icon="error" title="保存失败" :sub-title="store.saveError">
            <template #extra>
              <el-button @click="store.currentStep = 'preview'">返回预览</el-button>
              <el-button type="primary" @click="handleReset">重新生成</el-button>
            </template>
          </el-result>
        </el-card>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑用例" width="700px" destroy-on-close>
      <el-form v-if="editingCase" label-width="90px" size="default">
        <el-form-item label="标题" required>
          <el-input v-model="editingCase.title" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="editingCase.module" maxlength="100" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editingCase.priority">
            <el-option label="高" :value="1" />
            <el-option label="中" :value="2" />
            <el-option label="低" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="前置条件">
          <el-input v-model="editingCase.precondition" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="步骤" required>
          <div class="edit-steps">
            <div v-for="(step, i) in editingCase.steps" :key="i" class="edit-step-row">
              <el-input-number :model-value="i + 1" disabled :controls="false" style="width: 48px" />
              <el-input :model-value="(step as Record<string, unknown>).action as string" @update:model-value="updateStepField(i, 'action', $event)" placeholder="操作" style="flex: 2" />
              <el-input :model-value="(step as Record<string, unknown>).expected_result as string || ''" @update:model-value="updateStepField(i, 'expected_result', $event)" placeholder="预期结果" style="flex: 2" />
              <el-button text type="danger" @click="removeEditStep(i)">删除</el-button>
            </div>
            <el-button size="small" @click="addEditStep">+ 添加步骤</el-button>
          </div>
        </el-form-item>
        <el-form-item label="预期结果" required>
          <el-input v-model="editingCase.expected_result" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存修改</el-button>
      </template>
    </el-dialog>

    <!-- UI 上传对话框 -->
    <el-dialog v-model="store.uiUploadDialogVisible" title="上传 UI 页面" width="500px" destroy-on-close>
      <el-upload
        ref="uiUploadRef"
        action=""
        :auto-upload="false"
        :limit="20"
        :multiple="true"
        accept=".png,.jpg,.jpeg,.gif,.webp,.bmp"
        drag
        :on-change="handleUIFileChange"
      >
        <el-icon :size="48" color="#c0c4cc"><Upload /></el-icon>
        <div>拖拽或点击上传 UI 页面截图</div>
        <template #tip>
          <div class="upload-tip">支持 PNG/JPG/GIF/WebP/BMP，单次最多 20 张</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="store.uiUploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="store.uiUploading" @click="handleUIUploadSubmit">上传并解析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, WarningFilled, Loading, Upload, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSmartGenerationStore } from '@/store/smartGeneration'
import type { QualityStatus, SmartPreviewCase } from '@/store/smartGeneration'
import request from '@/utils/request'

const router = useRouter()
const store = useSmartGenerationStore()

const projects = ref<{ id: number; name: string }[]>([])
const requirementFiles = ref<{ id: number; file_name: string; original_name: string }[]>([])
const testPoints = ref<{ id: number; name: string; test_point: string; module: string }[]>([])

const saveMode = ref<'draft' | 'formal' | 'passed_only'>('draft')

const uiUploadFiles = ref<File[]>([])

const unparsedScreenIds = computed(() => {
  return store.uiScreenDetails
    .filter((s) => s.parse_status === 'pending' || s.parse_status === 'failed')
    .map((s) => s.id)
})

const editDialogVisible = ref(false)
const editingCase = ref<SmartPreviewCase | null>(null)
const editingClientId = ref<string>('')

const stepIndex = computed(() => {
  const map: Record<string, number> = {
    task: 0, material: 1, context: 2, strategy: 3,
    generating: 4, preview: 5, save_confirm: 6, save_result: 7,
  }
  return map[store.currentStep] || 0
})

const canAnalyzeContext = computed(() => {
  return store.selectedProjectId && store.testPointIds.length > 0
})

const materialLevelType = computed(() => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | undefined> = { L3: 'success', L2: undefined, L1: 'warning', L0: 'danger' }
  return map[store.materialLevel] ?? 'info'
})

function qualityTagType(status: QualityStatus): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<QualityStatus, 'success' | 'warning' | 'info' | 'danger'> = { passed: 'success', warning: 'warning', pending_review: 'info', rejected: 'danger' }
  return map[status] || 'info'
}

function qualityLabel(status: QualityStatus) {
  const map: Record<QualityStatus, string> = { passed: '通过', warning: '有轻微问题', pending_review: '需要确认', rejected: '不建议保存' }
  return map[status] || status
}

function priorityLabel(p: number) {
  const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
  return map[p] || '中'
}

function parseStatusLabel(status: string | undefined) {
  const map: Record<string, string> = { completed: '已解析', pending: '待解析', running: '解析中', failed: '解析失败' }
  return map[status || 'pending'] || '待解析'
}

function confidenceLabel(confidence: string) {
  const map: Record<string, string> = { explicit: '精确匹配', ui_file: 'UI文件匹配', matched: '关键词匹配', adjacent: '相邻页面' }
  return map[confidence] || confidence
}

function handleUIFileChange(_file: unknown, fileList: unknown[]) {
  uiUploadFiles.value = fileList.map((f) => (f as { raw: File }).raw).filter(Boolean)
}

async function handleUIUploadSubmit() {
  if (uiUploadFiles.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  await store.uploadUIScreens(uiUploadFiles.value)
  uiUploadFiles.value = []
  store.uiUploadDialogVisible = false
  ElMessage.success('上传成功')
  const pendingIds = store.uiScreenDetails
    .filter((s) => s.parse_status === 'pending')
    .map((s) => s.id)
  if (pendingIds.length > 0) {
    await store.parseUIScreens(pendingIds)
  }
}

async function loadProjects() {
  try {
    const resp = await request.get('/api/v1/projects')
    const data = (resp as { data?: unknown })?.data || resp
    projects.value = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
  } catch { projects.value = [] }
}

async function loadProjectFiles() {
  if (!store.selectedProjectId) { requirementFiles.value = []; return }
  try {
    const resp = await request.get(`/api/v1/files?project_id=${store.selectedProjectId}&resource_type=requirement`)
    const data = (resp as { data?: unknown })?.data || resp
    requirementFiles.value = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
  } catch { requirementFiles.value = [] }
}

async function loadTestPoints() {
  if (!store.selectedProjectId) { testPoints.value = []; return }
  try {
    const resp = await request.get(`/api/v1/test-points?project_id=${store.selectedProjectId}&page=1&page_size=500`)
    const data = (resp as { data?: unknown })?.data || resp
    testPoints.value = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
  } catch { testPoints.value = [] }
}

watch(() => store.selectedProjectId, async (val) => {
  if (val) {
    await Promise.all([loadProjectFiles(), loadTestPoints(), store.loadUIPrototypeProjects()])
  } else {
    requirementFiles.value = []
    testPoints.value = []
  }
})

function goToMaterial() {
  store.currentStep = 'material'
}

function goToStrategy() {
  store.currentStep = 'strategy'
}

function goToCaseMigration() {
  router.push({ name: 'CaseMigration' })
}

function goToTestPointManagement() {
  router.push({ name: 'TestPointManagement' })
}

function goToCaseList() {
  router.push({ name: 'CaseList' })
}

async function handleAnalyzeContext() {
  if (!canAnalyzeContext.value) {
    ElMessage.warning('请选择项目和至少一个测试点')
    return
  }
  store.currentStep = 'context'
  try {
    await store.createBatch()
    await store.fetchContext()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '资料识别失败')
  }
}

async function handleStartGeneration() {
  store.currentStep = 'generating'
  await store.startGeneration()
  if (store.previewCases.length > 0) {
    store.currentStep = 'preview'
  } else if (!store.generating && store.generationProgress) {
    // generation failed, stay on generating step for recovery UI
  }
}

function handleCancelGeneration() {
  store.generating = false
  if (store.previewCases.length > 0) {
    store.currentStep = 'preview'
  } else {
    store.currentStep = 'strategy'
  }
}

async function handleRetryGeneration() {
  store.currentStep = 'generating'
  store.generationProgress = ''
  await store.startGeneration()
  if (store.previewCases.length > 0) {
    store.currentStep = 'preview'
  }
}

function handleRegenerate() {
  store.previewCases = []
  store.currentStep = 'strategy'
}

async function handleRegenerateSingle(clientId: string) {
  try {
    await store.regenerateSingleCase(clientId)
    ElMessage.success('重新生成完成')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '重新生成失败')
  }
}

function openEditDialog(c: SmartPreviewCase) {
  editingClientId.value = c.client_id
  editingCase.value = JSON.parse(JSON.stringify(c))
  editDialogVisible.value = true
}

function updateStepField(stepIndex: number, field: string, value: string) {
  if (!editingCase.value) return
  const steps = [...editingCase.value.steps]
  const step = { ...(steps[stepIndex] as Record<string, unknown>) }
  step[field] = value
  steps[stepIndex] = step
  editingCase.value.steps = steps
}

function removeEditStep(index: number) {
  if (!editingCase.value) return
  editingCase.value.steps.splice(index, 1)
}

function addEditStep() {
  if (!editingCase.value) return
  editingCase.value.steps.push({ step: editingCase.value.steps.length + 1, action: '', expected_result: '' })
}

function saveEdit() {
  if (!editingCase.value) return
  const target = store.previewCases.find((c) => c.client_id === editingClientId.value)
  if (target) {
    target.title = editingCase.value.title
    target.module = editingCase.value.module
    target.priority = editingCase.value.priority
    target.precondition = editingCase.value.precondition
    target.steps = editingCase.value.steps
    target.expected_result = editingCase.value.expected_result
    target.dirty = true
    store.recalcQualitySummary()
  }
  editDialogVisible.value = false
  ElMessage.success('修改已保存到预览')
}

async function handleSave() {
  if (saveMode.value === 'formal') {
    try {
      await ElMessageBox.confirm(
        '当前结果由 AI 生成，建议先保存为草稿并人工复核。确定要保存为正式用例吗？',
        '保存确认',
        { confirmButtonText: '确定保存', cancelButtonText: '取消', type: 'warning' },
      )
    } catch { return }
  }
  store.currentStep = 'save_result'
  await store.saveBatch(saveMode.value)
}

function handleReset() {
  store.reset()
  saveMode.value = 'draft'
}

function handleBack() {
  router.back()
}

onMounted(() => {
  loadProjects()
})
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
  border-top: 1px solid #ebeef5;
}

.task-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.task-card {
  border: 2px solid #e4e7ed;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fff;
}
.task-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64,158,255,0.15);
}
.task-card.active {
  border-color: #409eff;
  background: #ecf5ff;
}
.task-card.primary {
  border-color: #409eff;
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
  color: #909399;
  margin: 0 0 16px;
  font-size: 14px;
}
.task-tags {
  margin-bottom: 16px;
}
.task-tags .el-tag {
  margin: 0 4px;
}
.task-btn {
  width: 100%;
}

.material-form {
  max-width: 600px;
}
.empty-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.optional-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.ui-project-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.ui-screen-section {
  margin-top: 16px;
  border: 1px solid #e4e7ed;
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
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.ui-screen-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64,158,255,0.12);
}
.ui-screen-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.ui-screen-card.parse-failed {
  border-color: #f56c6c;
  opacity: 0.8;
}
.ui-screen-card.parse-pending {
  border-color: #e6a23c;
  opacity: 0.85;
}
.screen-thumb {
  width: 100%;
  height: 80px;
  overflow: hidden;
  border-radius: 4px;
  background: #f5f7fa;
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
  color: #909399;
}
.screen-error {
  font-size: 11px;
  color: #f56c6c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-ref-item {
  margin-right: 8px;
}
.upload-tip {
  font-size: 12px;
  color: #909399;
}
.advanced-collapse {
  max-width: 600px;
  margin-top: 16px;
}

.context-card, .warning-card, .evidence-card, .strategy-confirm .el-card {
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
  color: #606266;
  padding: 2px 6px;
  background: #f5f7fa;
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
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.progress-hint {
  color: #909399;
  margin-top: 12px;
}
.recovery-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.preview-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.coverage-collapse {
  margin-bottom: 16px;
}
.coverage-tag {
  margin: 2px 4px;
}
.preview-case-card {
  margin-bottom: 12px;
  border-left: 4px solid #e4e7ed;
}
.preview-case-card.quality-passed { border-left-color: #67c23a; }
.preview-case-card.quality-warning { border-left-color: #e6a23c; }
.preview-case-card.quality-pending_review { border-left-color: #409eff; }
.preview-case-card.quality-rejected { border-left-color: #f56c6c; }
.case-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.case-title {
  font-weight: 600;
  flex: 1;
  min-width: 120px;
}
.case-actions {
  margin-left: auto;
  white-space: nowrap;
}
.case-detail {
  margin-top: 8px;
}
.step-list {
  margin: 0;
  padding-left: 16px;
}
.step-list li {
  line-height: 1.8;
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
  color: #e6a23c;
  font-size: 13px;
  margin-top: 8px;
}

.failure-list {
  margin-top: 16px;
  text-align: left;
}
.failure-list h4 {
  margin: 0 0 8px;
}
.failure-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.result-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  justify-content: center;
}

.edit-steps {
  width: 100%;
}
.edit-step-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
