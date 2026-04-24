<template>
  <div class="ai-generate-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>AI生成测试用例</h2>
      <div class="header-actions">
        <el-button type="primary" plain @click="goToResourceManage">
          <el-icon><Upload /></el-icon>
          上传资源文件
        </el-button>
        <el-button @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
      </div>
    </div>

    <!-- 步骤指示器 -->
    <el-steps :active="currentStep" finish-status="success" class="steps-indicator">
      <el-step title="选择需求来源" description="关联需求文档和UI原型" />
      <el-step title="配置测试参数" description="选择用例类型和测试点" />
      <el-step title="生成并保存" description="AI生成详细测试用例" />
    </el-steps>

    <!-- 步骤1: 选择需求来源 -->
    <el-card v-if="currentStep === 0" class="step-card">
      <template #header>
        <div class="card-header">
          <span>选择需求来源</span>
          <el-tag type="info">可选步骤，不选择则使用手动输入</el-tag>
        </div>
      </template>

      <el-form label-width="120px">
        <el-form-item label="项目">
          <el-select
            v-model="formData.project_id"
            placeholder="请选择项目"
            style="width: 400px"
            filterable
            :loading="projectsLoading"
            @change="handleProjectChange"
            @focus="handleProjectFocus"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <!-- 需求文档选择 -->
        <el-form-item label="需求文档">
          <el-select
            v-model="formData.requirement_file_ids"
            multiple
            placeholder="选择需求文档（可多选）"
            style="width: 600px"
            collapse-tags
            collapse-tags-tooltip
          >
            <el-option
              v-for="file in requirementFiles"
              :key="file.id"
              :label="file.file_name"
              :value="file.id"
            >
              <span>{{ file.file_name }}</span>
              <el-tag size="small" type="primary" style="margin-left: 8px">{{
                file.extract_status === 'completed' ? '已提取' : file.extract_status
              }}</el-tag>
            </el-option>
          </el-select>
          <el-button
            type="primary"
            plain
            size="small"
            @click="extractFileContent"
            :loading="fetchingRequirement"
            style="margin-left: 10px"
          >
            提取内容
          </el-button>
          <el-button
            type="success"
            plain
            size="small"
            @click="goToResourceManage"
            style="margin-left: 10px"
          >
            上传文件
          </el-button>
        </el-form-item>

        <!-- UI原型图版本选择 -->
        <el-form-item label="UI原型图">
          <div class="ui-mockup-section">
            <el-alert
              title="选择UI原型图版本（可选）"
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 16px"
            >
              <template #default>
                选择不同版本的UI原型图，下方可查看和调整屏幕顺序。 点击图片可预览大图。
              </template>
            </el-alert>

            <div class="version-selector">
              <el-select
                v-model="selectedUiPrototypeProjectId"
                placeholder="请选择UI原型图版本"
                style="width: 100%"
                @change="handleUIPrototypeProjectChange"
                :disabled="!formData.project_id"
                clearable
              >
                <el-option
                  v-for="project in uiPrototypeProjects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                >
                  <div class="version-option">
                    <span class="version-name">{{ project.name }}</span>
                    <el-tag v-if="project.parse_status === 'completed'" type="success" size="small">
                      ✓ 已解析
                    </el-tag>
                    <el-tag
                      v-else-if="project.parse_status === 'partial'"
                      type="warning"
                      size="small"
                    >
                      部分解析 ({{ project.parsed_count }}/{{ project.screen_count }})
                    </el-tag>
                    <el-tag
                      v-else-if="project.parse_status === 'failed'"
                      type="danger"
                      size="small"
                    >
                      ✗ 解析失败
                    </el-tag>
                    <el-tag v-else type="info" size="small"> 待解析 </el-tag>
                  </div>
                </el-option>
              </el-select>
              <el-button
                type="primary"
                plain
                @click="loadUIPrototypeProjects"
                :disabled="!formData.project_id"
                style="margin-left: 12px"
              >
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </div>
        </el-form-item>

        <!-- UI屏幕预览和排序区域 -->
        <el-form-item
          label="屏幕预览"
          v-if="selectedUiPrototypeProjectId"
          class="screen-preview-form-item"
        >
          <el-alert
            v-if="
              selectedUiPrototypeProject &&
              selectedUiPrototypeProject.parse_status !== 'completed' &&
              showParseWarning
            "
            :title="
              selectedUiPrototypeProject.parse_status === 'partial'
                ? `该UI原型图部分解析（${selectedUiPrototypeProject.parsed_count}/${selectedUiPrototypeProject.screen_count}），未解析的屏幕将无法获取详细元素信息`
                : '该UI原型图尚未解析，将无法获取详细的按钮、输入框等元素信息，建议先在资源管理中进行解析'
            "
            type="warning"
            show-icon
            closable
            style="margin-bottom: 16px"
            @close="showParseWarning = false"
          />
          <div v-if="uiScreens.length > 0" class="screen-preview-wrapper">
            <div class="screen-preview-overview">
              <div class="preview-overview-main">
                <div class="preview-overview-title">
                  <span class="preview-overview-name">{{
                    selectedUiPrototypeProject?.name || '当前UI版本'
                  }}</span>
                  <el-tag size="small" type="info" effect="plain"
                    >共 {{ uiScreens.length }} 个屏幕</el-tag
                  >
                  <el-tag size="small" :type="screenPreviewStatusType" effect="plain">
                    {{ screenPreviewStatusText }}
                  </el-tag>
                </div>
                <div class="preview-overview-desc">
                  点击缩略图可查看大图；拖拽节点可调整页面顺序，连线可补充页面流转关系。
                </div>
              </div>
              <div class="preview-overview-tips">
                <div class="preview-tip-item">
                  <el-icon><View /></el-icon>
                  <span>点击预览</span>
                </div>
                <div class="preview-tip-item">
                  <el-icon><Rank /></el-icon>
                  <span>拖拽调整顺序</span>
                </div>
              </div>
            </div>
            <FlowSortEditor
              ref="flowSortEditorRef"
              class="screen-sort-editor"
              :screens="uiScreens"
              :screen-image-urls="screenImageUrls"
              :module-info="flowSortModuleInfo"
              @update:sort-data="handleFlowSortUpdate"
              @preview-prompt="handlePreviewPrompt"
              @preview-screen="handleFlowNodePreview"
            />
          </div>
          <div v-else class="ui-screens-empty">
            <el-empty description="该版本暂无屏幕" />
          </div>
        </el-form-item>

        <!-- 测试点选择 -->
        <el-form-item label="测试点">
          <div class="test-point-selector" :class="{ 'has-data': testPointTotal > 0 }">
            <!-- 头部工具栏 -->
            <div class="tp-toolbar" v-if="testPointTotal > 0 || formData.test_point_ids.length > 0">
              <div class="tp-toolbar-left">
                <span class="tp-stat" v-if="testPointTotal > 0"
                  >共 <strong>{{ testPointTotal }}</strong> 条</span
                >
                <el-tag
                  size="small"
                  type="primary"
                  effect="dark"
                  v-if="formData.test_point_ids.length > 0"
                >
                  已选 {{ formData.test_point_ids.length }}
                </el-tag>
              </div>
              <div class="tp-toolbar-right">
                <el-button
                  link
                  type="primary"
                  size="small"
                  @mousedown.prevent
                  @click.stop.prevent="selectAllTestPoints"
                  :disabled="testPointAllIds.length === 0"
                >
                  全选
                </el-button>
                <el-button
                  link
                  type="danger"
                  size="small"
                  @mousedown.prevent
                  @click.stop.prevent="deselectAllTestPoints"
                  :disabled="formData.test_point_ids.length === 0"
                >
                  清空
                </el-button>
              </div>
            </div>

            <!-- 选择器 -->
            <el-select
              :key="testPointSelectKey"
              v-model="formData.test_point_ids"
              multiple
              filterable
              placeholder="点击选择或搜索测试点（可选，不选则使用手动输入）"
              class="tp-select"
              popper-class="tp-dropdown"
              collapse-tags
              collapse-tags-tooltip
              :max-collapse-tags="2"
            >
              <!-- 下拉头部 -->
              <template #header>
                <div class="tp-d-header" @mousedown.prevent>
                  <div class="tp-d-search">
                    <el-icon><Search /></el-icon>
                    <input placeholder="搜索..." />
                  </div>
                  <div class="tp-d-info">
                    <span
                      >{{ testPointPage }}/{{
                        Math.ceil(testPointTotal / testPointPageSize) || 1
                      }}</span
                    >
                    <el-button
                      link
                      size="small"
                      type="primary"
                      @mousedown.prevent
                      @click.stop.prevent="selectCurrentPageAll"
                    >
                      本页全选
                    </el-button>
                  </div>
                </div>
              </template>

              <!-- 选项列表 -->
              <el-option
                v-for="point in testPoints"
                :key="point.id"
                :label="`${point.module} - ${point.function}`"
                :value="point.id"
                :class="{ 'is-checked': formData.test_point_ids.includes(point.id) }"
                @click.stop
              >
                <div class="tp-item" @mousedown.prevent @click.stop>
                  <label class="tp-check" @mousedown.prevent @click.stop>
                    <input
                      type="checkbox"
                      :checked="formData.test_point_ids.includes(point.id)"
                      @click.stop
                      @change="
                        (e: Event) => {
                          ;(e.target as HTMLInputElement).checked
                            ? addTestPoint(point.id)
                            : removeTestPoint(point.id)
                        }
                      "
                    />
                  </label>
                  <div class="tp-content">
                    <div class="tp-row1">
                      <span class="tp-mod">{{ point.module }}</span>
                      <span class="tp-sep">/</span>
                      <span class="tp-func">{{ point.function }}</span>
                      <el-tag
                        size="small"
                        :type="getPriorityType(point.priority)"
                        round
                        class="tp-pri"
                      >
                        {{ getPriorityLabel(point.priority) }}
                      </el-tag>
                    </div>
                    <div class="tp-row2">{{ point.point }}</div>
                  </div>
                </div>
              </el-option>

              <!-- 底部分页 -->
              <template #footer v-if="testPointTotal > 0">
                <div class="tp-d-footer" @mousedown.prevent>
                  <el-pagination
                    :current-page="testPointPage"
                    :page-size="testPointPageSize"
                    :total="testPointTotal"
                    layout="prev, pager, next, jumper"
                    size="small"
                    @current-change="goToTestPointPage"
                  />
                </div>
              </template>

              <template #empty>
                <div class="tp-empty">
                  <p>请先选择需求文档</p>
                </div>
              </template>
            </el-select>

            <!-- 已选标签 -->
            <transition name="el-fade-in-linear">
              <div class="tp-chips" v-if="formData.test_point_ids.length > 0">
                <el-tag
                  v-for="id in formData.test_point_ids.slice(0, 6)"
                  :key="id"
                  closable
                  effect="dark"
                  :type="getSelectedTagType(id)"
                  size="small"
                  @close="removeTestPoint(id)"
                  >{{ getTestPointLabel(id) }}</el-tag
                >
                <el-popover
                  v-if="formData.test_point_ids.length > 6"
                  placement="bottom-start"
                  :width="280"
                  trigger="hover"
                >
                  <template #reference>
                    <el-tag effect="dark" type="info" round size="small"
                      >+{{ formData.test_point_ids.length - 6 }}</el-tag
                    >
                  </template>
                  <div style="max-height: 200px; overflow-y: auto; padding: 4px 0">
                    <el-tag
                      v-for="id in formData.test_point_ids.slice(6)"
                      :key="id"
                      closable
                      effect="dark"
                      :type="getSelectedTagType(id)"
                      size="small"
                      style="margin: 2px"
                      @close="removeTestPoint(id)"
                    >
                      {{ getTestPointLabel(id) }}
                    </el-tag>
                  </div>
                </el-popover>
              </div>
            </transition>
          </div>
        </el-form-item>

        <!-- 已选择的上下文信息展示 -->
        <el-form-item label="上下文预览" v-if="contextPreview">
          <div class="context-preview">
            <el-alert
              :title="contextPreview.title"
              :type="contextPreview.type"
              show-icon
              :closable="false"
            >
              <template #default>
                <div v-if="contextPreview.requirement">
                  需求文档: {{ contextPreview.requirement }}
                </div>
                <div v-if="contextPreview.ui">UI原型: {{ contextPreview.ui }}</div>
                <div v-if="contextPreview.uiSpecs">
                  已解析UI规格: {{ contextPreview.uiSpecs }}个页面
                </div>
                <div v-if="contextPreview.testPoints">测试点: {{ contextPreview.testPoints }}</div>
              </template>
            </el-alert>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="nextStep">
            下一步：配置测试参数
            <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button @click="skipToStep2">跳过，直接手动输入</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 步骤2: 配置测试参数 -->
    <el-card v-if="currentStep === 1" class="step-card">
      <template #header>
        <div class="card-header">
          <span>配置测试参数</span>
          <el-button size="small" @click="prevStep">上一步</el-button>
        </div>
      </template>

      <el-form :model="formData" label-width="120px">
        <!-- 已选测试点预览（替代手动输入场景） -->
        <el-form-item label="待生成范围">
          <div class="scope-preview">
            <div class="scope-stats">
              <el-statistic title="已选测试点" :value="formData.test_point_ids.length" />
              <el-statistic
                title="需求文档"
                :value="formData.requirement_file_ids.length"
                class="stat-docs"
              />
              <el-statistic
                title="UI原型"
                :value="formData.ui_screen_ids.length || formData.ui_file_ids.length"
                class="stat-ui"
              />
            </div>
            <div class="scope-testpoints" v-if="selectedTestPointsForDisplay.length > 0">
              <div class="st-list">
                <div v-for="tp in selectedTestPointsForDisplay" :key="tp.id" class="st-item">
                  <span class="st-mod">{{ tp.module }}</span>
                  <span class="st-sep">/</span>
                  <span class="st-func">{{ tp.function }}</span>
                  <span class="st-point">{{ tp.point }}</span>
                  <el-tag size="small" :type="getPriorityType(tp.priority)" round>{{
                    getPriorityLabel(tp.priority)
                  }}</el-tag>
                </div>
              </div>
              <div class="st-more" v-if="formData.test_point_ids.length > 5">
                还有 {{ formData.test_point_ids.length - 5 }} 个测试点未展示...
              </div>
            </div>
            <el-alert v-else type="info" :closable="false" show-icon style="margin-top: 8px">
              AI 将基于所选需求文档和测试点自动分析并生成测试用例，无需手动描述场景
            </el-alert>
          </div>
        </el-form-item>

        <!-- 用例类型（主分类 + 执行方式子分类） -->
        <el-form-item label="用例类型">
          <div class="case-type-group">
            <el-select
              v-model="formData.case_type"
              placeholder="请选择用例类型（不选择则由AI智能判断）"
              style="width: 180px"
              @change="handleCaseTypeChange"
            >
              <el-option label="UI自动化" value="ui_automation" />
              <el-option label="手工测试" value="manual" />
              <el-option label="API自动化" value="api_automation" />
              <el-option label="性能测试" value="performance" />
              <el-option label="安全测试" value="security" />
            </el-select>

            <!-- UI自动化的执行方式细分 -->
            <div class="exec-mode-group" v-if="formData.case_type === 'ui_automation'">
              <span class="exec-label">执行方式：</span>
              <el-radio-group v-model="formData.exec_mode" size="small">
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
              v-if="formData.case_type === 'api_automation'"
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
              v-if="formData.case_type === 'performance'"
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
              v-if="formData.case_type === 'security'"
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

        <!-- 补充说明（可选） -->
        <el-form-item label="补充要求">
          <el-input
            v-model="formData.extra_requirements"
            type="textarea"
            :rows="3"
            placeholder="可选：补充特殊要求，如&#10;• 需覆盖弱网/断网等异常场景&#10;• 需包含边界值测试&#10;• 兼容 Chrome/Firefox/Safari"
          />
          <div class="form-tip" style="margin-top: 4px">
            不填则由 AI 根据测试点智能判断，通常无需填写
          </div>
        </el-form-item>

        <el-form-item label="优先级">
          <el-select v-model="formData.priority" placeholder="请选择优先级">
            <el-option label="P0-高（核心流程）" :value="1" />
            <el-option label="P2-中（主要功能）" :value="2" />
            <el-option label="P3-低（边缘场景）" :value="3" />
          </el-select>
        </el-form-item>

        <el-form-item label="增强模式">
          <el-switch v-model="formData.enhanced_mode" active-text="启用" inactive-text="禁用" />
          <span class="form-tip">启用后生成含具体测试数据、断言规则的详细用例</span>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            @click="handleGenerate"
            :loading="generating"
            :disabled="canGenerate === false"
          >
            <el-icon><MagicStick /></el-icon>
            开始生成 ({{ generateButtonLabel }})
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 生成进度 -->
    <el-card v-if="generating" class="progress-card">
      <template #header>
        <div class="card-header">
          <span>生成进度</span>
        </div>
      </template>

      <div class="progress-container">
        <el-progress :percentage="progress" :status="progressStatus" :stroke-width="20" />
        <div class="progress-text">{{ progressText }}</div>
        <el-button type="danger" @click="handleCancel" v-if="generating">
          <el-icon><Close /></el-icon>
          取消生成
        </el-button>
      </div>
    </el-card>

    <!-- 生成结果 -->
    <el-card v-if="generatedCases.length > 0 && !generating" class="result-card">
      <template #header>
        <div class="card-header">
          <span
            >生成结果
            <el-tag size="small" type="info"
              >{{ currentCaseIndex + 1 }}/{{ generatedCases.length }}</el-tag
            ></span
          >
          <div class="result-actions">
            <el-button v-if="!isEditingResult" type="warning" size="small" @click="startEditResult">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <template v-else>
              <el-button type="success" size="small" @click="handleSaveCase">
                <el-icon><Check /></el-icon>保存
              </el-button>
              <el-button size="small" @click="cancelEditResult">取消</el-button>
            </template>
            <el-button
              v-if="!isEditingResult"
              type="primary"
              size="small"
              @click="handleSaveCase"
              :loading="saving"
            >
              <el-icon><Check /></el-icon>保存用例
            </el-button>
          </div>
        </div>
      </template>

      <!-- 用例导航条 -->
      <div class="case-nav-bar" v-if="generatedCases.length > 1 && !isEditingResult">
        <button class="case-nav-btn" :disabled="currentCaseIndex <= 0" @click="currentCaseIndex--">
          ‹ 上一条
        </button>
        <div class="case-nav-dots">
          <span
            v-for="(c, idx) in generatedCases"
            :key="idx"
            class="case-dot"
            :class="{ active: idx === currentCaseIndex, error: c._error, saved: c._saved }"
            @click="currentCaseIndex = idx"
            :title="c.title"
            >{{ idx + 1 }}</span
          >
        </div>
        <button
          class="case-nav-btn"
          :disabled="currentCaseIndex >= generatedCases.length - 1"
          @click="currentCaseIndex++"
        >
          下一条 ›
        </button>
        <div class="case-batch-actions">
          <el-button
            type="success"
            size="small"
            @click="saveAllCases"
            :loading="saving"
            :disabled="generatedCases.every((c) => c._error || c._saved)"
          >
            全部保存 ({{ generatedCases.filter((c) => !c._error && !c._saved).length }})
          </el-button>
        </div>
      </div>

      <!-- 错误提示（单条失败） -->
      <el-alert
        v-if="viewingCase?._error"
        :title="'生成失败: ' + viewingCase._error"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />

      <template v-if="!isEditingResult && viewingCase">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用例名称">{{ viewingCase.title }}</el-descriptions-item>
          <el-descriptions-item label="关联测试点">
            <el-tag size="small" type="info">{{ viewingCase.test_point_label || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用例类型">
            <el-tag :type="getTypeTagType(viewingCase.case_type)" size="small">
              {{ getTypeLabel(viewingCase.case_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityTagType(viewingCase.priority)" size="small">
              {{ getPriorityLabel(viewingCase.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模块">{{ viewingCase.module || '-' }}</el-descriptions-item>
          <el-descriptions-item label="前置条件" :span="2">{{
            viewingCase.precondition || '-'
          }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-else-if="isEditingResult">
        <div class="edit-form-grid">
          <div class="edit-field">
            <label>用例名称 *</label>
            <el-input v-model="editingCase.title" placeholder="请输入用例名称" />
          </div>
          <div class="edit-field">
            <label>模块</label>
            <el-input v-model="editingCase.module" placeholder="请输入模块名称" />
          </div>
          <div class="edit-field">
            <label>用例类型</label>
            <el-select v-model="editingCase.case_type" style="width: 100%">
              <el-option label="UI自动化" value="ui_automation" />
              <el-option label="手工测试" value="manual" />
              <el-option label="API自动化" value="api_automation" />
              <el-option label="性能测试" value="performance" />
              <el-option label="安全测试" value="security" />
            </el-select>
          </div>
          <div class="edit-field">
            <label>优先级</label>
            <el-select v-model="editingCase.priority" style="width: 100%">
              <el-option label="P0-高" value="P0" />
              <el-option label="P2-中" value="P2" />
              <el-option label="P3-低" value="P3" />
            </el-select>
          </div>
          <div class="edit-field full-width">
            <label>前置条件</label>
            <el-input
              v-model="editingCase.precondition"
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
          viewingCase?.test_data &&
          Object.keys(viewingCase.test_data).length > 0 &&
          !isEditingResult
        "
        class="test-data-section"
      >
        <h3>测试数据</h3>
        <el-row :gutter="20">
          <el-col :span="8" v-for="(data, key) in viewingCase.test_data" :key="key">
            <el-card shadow="hover" class="test-data-card">
              <template #header>
                <span class="test-data-title">{{ getDataTypeLabel(key) }}</span>
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
            v-if="isEditingResult"
            type="primary"
            size="small"
            @click="addEditStep"
            style="margin-left: 10px"
            >+ 添加步骤</el-button
          >
        </h3>
        <template v-if="!isEditingResult && viewingCase">
          <el-timeline>
            <el-timeline-item
              v-for="(step, index) in viewingCase.steps"
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
                    <strong>预期结果:</strong> {{ cleanExpectedResult(step.expected_result) }}
                  </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <div v-if="!viewingCase.steps || viewingCase.steps.length === 0" class="empty-steps">
            <el-empty description="暂无测试步骤" />
          </div>
        </template>

        <template v-else>
          <div class="editable-steps-list">
            <div v-for="(step, index) in editingCase.steps" :key="index" class="editable-step-card">
              <div class="step-card-header">
                <span class="step-num">步骤 {{ Number(index) + 1 }}</span>
                <el-button
                  type="danger"
                  size="small"
                  @click="removeEditStep(Number(index))"
                  :disabled="editingCase.steps.length <= 1"
                  >删除</el-button
                >
              </div>
              <div class="step-card-body">
                <div class="step-edit-field">
                  <label>操作描述：</label
                  ><el-input v-model="step.action" placeholder="请输入操作描述" />
                </div>
                <div class="step-edit-field">
                  <label>预期结果：</label
                  ><el-input v-model="step.expected_result" placeholder="请输入预期结果" />
                </div>
                <div class="step-edit-field">
                  <label>测试数据/参数：</label><el-input v-model="step.param" placeholder="可选" />
                </div>
              </div>
            </div>
            <div v-if="editingCase.steps.length === 0" class="empty-steps-hint">
              <p>暂无步骤，点击上方"添加步骤"</p>
            </div>
          </div>
        </template>
      </div>

      <!-- 总体预期结果 -->
      <div v-if="viewingCase?.expected_result && !isEditingResult" class="expected-result-section">
        <h3>总体预期结果</h3>
        <el-alert
          :title="cleanExpectedResult(viewingCase.expected_result)"
          type="success"
          :closable="false"
          show-icon
        />
      </div>
      <div v-else-if="isEditingResult" class="expected-result-section">
        <h3>总体预期结果</h3>
        <el-input
          v-model="editingCase.expected_result"
          type="textarea"
          :rows="2"
          placeholder="请输入总体预期结果"
        />
      </div>

      <div class="result-actions-bottom" v-if="!isEditingResult">
        <el-button @click.stop="currentStep = 1">修改配置</el-button>
        <el-button type="primary" @click="handleSaveCase" :loading="saving">保存当前用例</el-button>
        <el-button type="success" @click="handleContinueGenerate" :loading="generating"
          >基于此用例继续生成</el-button
        >
      </div>
    </el-card>

    <!-- 错误提示 -->
    <el-card v-if="errorMessage" class="error-card">
      <template #header>
        <div class="card-header">
          <span>生成失败</span>
        </div>
      </template>

      <div class="error-content">
        <el-alert :title="errorMessage" type="error" show-icon :closable="false" />
        <div v-if="errorSuggestions.length > 0" class="error-suggestions">
          <h4>优化建议：</h4>
          <ul>
            <li v-for="(suggestion, index) in errorSuggestions" :key="index">{{ suggestion }}</li>
          </ul>
        </div>
        <el-button type="primary" @click="handleRetry" style="margin-top: 15px">
          <el-icon><Refresh /></el-icon>
          重试
        </el-button>
      </div>
    </el-card>

    <!-- 图片预览 -->
    <el-image-viewer
      v-if="isPreviewImageVisible"
      :url-list="[previewImageUrl]"
      :initial-index="0"
      @close="isPreviewImageVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  MagicStick,
  Close,
  Check,
  Refresh,
  Upload,
  Search,
  InfoFilled,
  Edit,
  Rank,
  View,
} from '@element-plus/icons-vue'
import { testPointApi, type TestPoint } from '@/api/testPoint'
import { fileApi, type ProjectFile } from '@/api/file'
import { type Project } from '@/api/project'
import caseApi from '../../api/case'
import request, { type ApiResponse } from '@/utils/request'
import { uiPrototypeApi, type UIPrototypeProject, type UIScreen } from '@/api/uiPrototype'
import FlowSortEditor from '@/components/case/FlowSortEditor.vue'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'

const router = useRouter()
const route = useRoute()

let _caseNoCounter = 0

function generateCaseNo(projectId: number | '', extraSuffix?: number): string {
  _caseNoCounter++
  const ts = Date.now()
  const suffix = extraSuffix != null ? `-${extraSuffix}` : ''
  return `CASE${String(projectId)}-${ts}-${_caseNoCounter}${suffix}`
}

function normalizePriority(priority: any): number {
  if (typeof priority === 'number') {
    if (priority < 1) return 1
    if (priority > 3) return 3
    return priority
  }
  const pMap: Record<string, number> = { P0: 1, P2: 2, P3: 3, '1': 1, '2': 2, '3': 3 }
  return pMap[String(priority)] || 2
}

// 状态
const currentStep = ref(0)
const generating = ref(false)
const saving = ref(false)
const progress = ref(0)
const progressText = ref('准备生成...')
const errorMessage = ref('')
const errorSuggestions = ref<string[]>([])

// 项目和文件
const projects = ref<any[]>([])
const projectsLoading = ref(false)
const projectsLoaded = ref(false)
const requirementFiles = ref<ProjectFile[]>([])
const uiFiles = ref<ProjectFile[]>([])
const testPoints = ref<any[]>([])

// UI 原型相关
const uiPrototypeProjects = ref<UIPrototypeProject[]>([])
const selectedUiPrototypeProjectId = ref<number | ''>('')
const selectedUiPrototypeProject = computed(() => {
  if (!selectedUiPrototypeProjectId.value) return null
  return uiPrototypeProjects.value.find((p) => p.id === selectedUiPrototypeProjectId.value) || null
})
const uiScreens = ref<UIScreen[]>([])
const screenImageUrls = ref<Record<number, string>>({})
const previewImageUrl = ref('')
const isPreviewImageVisible = ref(false)
const showParseWarning = ref(true)

const flowSortEditorRef = ref<InstanceType<typeof FlowSortEditor> | null>(null)

type FlowSortValidationResult = {
  errors: string[]
  warnings: string[]
}

type FlowSortEditorExpose = InstanceType<typeof FlowSortEditor> & {
  getFlowSortSubmitData?: () => {
    mode: 'graph'
    flow_sort_data: Record<string, any>
  }
  getFlowValidationIssues?: () => FlowSortValidationResult
}

const flowSortModuleInfo = computed(() => {
  if (!selectedUiPrototypeProject.value) return { name: '', description: '' }
  return {
    name: selectedUiPrototypeProject.value.name || '',
    description: selectedUiPrototypeProject.value.description || '',
  }
})

const screenPreviewStatusType = computed(() => {
  const status = selectedUiPrototypeProject.value?.parse_status
  if (status === 'completed') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
})

const screenPreviewStatusText = computed(() => {
  const project = selectedUiPrototypeProject.value
  if (!project) return '未选择版本'
  if (project.parse_status === 'completed') return '全部已解析'
  if (project.parse_status === 'partial') {
    return `部分解析 ${project.parsed_count || 0}/${project.screen_count || uiScreens.value.length}`
  }
  if (project.parse_status === 'failed') return '解析失败'
  return '待解析'
})

const handleFlowSortUpdate = (data: {
  mode: string
  nodes: FlowNodeData[]
  edges: FlowEdgeData[]
}) => {
  formData.ui_screen_ids = data.nodes.map((n) => n.screen_id)
}

const handlePreviewPrompt = () => {
  const editor = flowSortEditorRef.value as FlowSortEditorExpose | null
  const validation = editor?.getFlowValidationIssues?.()
  if (validation?.errors.length) {
    ElMessage.warning(validation.errors[0])
    return
  }
  if (validation?.warnings.length) {
    ElMessage.warning(validation.warnings[0])
  }

  const submitData = editor?.getFlowSortSubmitData?.()
  if (submitData?.flow_sort_data) {
    console.log('[Prompt预览] flow_sort_data:', JSON.stringify(submitData.flow_sort_data, null, 2))
    ElMessage.info('Prompt 数据已输出到控制台')
  } else {
    ElMessage.warning('当前尚未生成页面流程数据')
  }
}

const handleFlowNodePreview = (screenData: {
  screen_id: number
  screen_name: string
  image_url?: string
}) => {
  const screen = uiScreens.value.find((s) => s.id === screenData.screen_id)
  if (screen && screenImageUrls.value[screen.id]) {
    previewImageUrl.value = screenImageUrls.value[screen.id]
    isPreviewImageVisible.value = true
  }
}

// 测试点分页
const testPointPage = ref(1)
const testPointPageSize = ref(10)
const testPointTotal = ref(0)
const testPointAllIds = ref<number[]>([])
const testPointSelectKey = ref(0)
const isLoadingMore = ref(false)
const TEST_POINT_CACHE_MAX = 500
const testPointCache = reactive(new Map<number, any>())

// 获取状态
const fetchingRequirement = ref(false)

// 上下文预览
const contextPreview = ref<any>(null)
const lastContext = ref<Record<string, any>>({})

// 生成的用例列表（每个测试点生成一条）
const generatedCases = ref<any[]>([])
const currentCaseIndex = ref<number>(-1)
const isEditingResult = ref(false)
const editingCase = ref<any>({
  title: '',
  module: '',
  case_type: '功能测试',
  precondition: '',
  expected_result: '',
  priority: 2,
  steps: [] as any[],
})

// 当前正在查看的用例（从列表中取）
const viewingCase = computed(() => {
  if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
    return generatedCases.value[currentCaseIndex.value]
  }
  return generatedCases.value[0] || null
})

// 表单数据
const formData = reactive({
  project_id: '' as number | '',
  requirement_file_ids: [] as number[],
  ui_file_ids: [] as number[],
  ui_screen_ids: [] as number[],
  test_point_ids: [] as number[],
  test_points_data: [] as any[],
  scene: '',
  case_type: '',
  exec_mode: 'all' as 'all' | 'ui_auto' | 'manual',
  priority: 2,
  enhanced_mode: true,
  extra_requirements: '',
})

// 已选测试点预览（最多展示5条）
const selectedTestPointsForDisplay = computed(() => {
  const ids = formData.test_point_ids.slice(0, 5)
  return ids.map((id) => {
    const tp =
      testPoints.value.find((p) => p.id === id) ||
      formData.test_points_data.find((p: any) => p.id === id)
    return tp || { id, module: '?', function: '?', point: '未知测试点', priority: 2 }
  })
})

// 是否可以生成
const canGenerate = computed(() => {
  return (
    formData.test_point_ids.length > 0 ||
    formData.requirement_file_ids.length > 0 ||
    formData.ui_file_ids.length > 0 ||
    formData.ui_screen_ids.length > 0
  )
})

// 生成按钮标签
const generateButtonLabel = computed(() => {
  const count = formData.test_point_ids.length
  if (count > 0) return `${count} 个测试用例`
  if (formData.requirement_file_ids.length > 0)
    return `${formData.requirement_file_ids.length} 份需求`
  if (formData.case_type === 'api_automation') return '接口用例'
  return '开始'
})

const handleCaseTypeChange = (val: string) => {
  if (val !== 'ui_automation') {
    formData.exec_mode = 'all'
  }
}

// 计算属性
const progressStatus = computed(() => {
  if (progress.value === 100) return 'success'
  if (errorMessage.value) return 'exception'
  return ''
})

// 获取项目列表
const getProjects = async (forceReload: boolean = false) => {
  if (projectsLoaded.value && !forceReload && projects.value.length > 0) {
    return
  }
  projectsLoading.value = true
  try {
    const response: ApiResponse<{ items: Project[]; total: number }> = await request.get(
      '/api/v1/project/list',
      {
        params: { page: 1, page_size: 1000 },
      }
    )
    if (response && response.data && response.data.items) {
      projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
      projectsLoaded.value = true
    }
  } catch (error) {
    console.error('获取项目列表失败:', error)
  } finally {
    projectsLoading.value = false
  }
}

// 加载项目文件（需求文档和UI原型图）
const loadProjectFiles = async () => {
  try {
    const response = await fileApi.getFileList(formData.project_id as number)
    const items = extractListItems(response)
    // 根据 resource_type 分类
    requirementFiles.value = items.filter((f: any) => f.resource_type === 'requirement')
    uiFiles.value = items.filter((f: any) => f.resource_type === 'ui_mockup')
  } catch (error) {
    console.error('获取文件列表失败:', error)
  }
}

/** 文件列表等接口：分页体在根上或包在 data 内 */
function extractListItems(res: any): any[] {
  if (!res || typeof res !== 'object') return []
  if (Array.isArray(res)) return res
  if (Array.isArray(res.items)) return res.items
  const d = res.data
  if (d && Array.isArray(d.items)) return d.items
  return []
}

// 加载测试点（根据需求文档关联的测试点）
const loadTestPoints = async (
  page: number = 1,
  append: boolean = false,
  refreshKey: boolean = true
) => {
  if (!formData.project_id) return

  try {
    const apiData = await testPointApi.getList(formData.project_id as number, {
      page,
      page_size: testPointPageSize.value,
    })

    if (apiData) {
      const newItems = apiData.items || []
      if (append && page > 1) {
        testPoints.value = [...testPoints.value, ...newItems]
      } else {
        testPoints.value = newItems
      }

      newItems.forEach((item: any) => {
        testPointCache.set(item.id, item)
        if (!testPointAllIds.value.includes(item.id)) {
          testPointAllIds.value.push(item.id)
        }
      })

      if (testPointCache.size > TEST_POINT_CACHE_MAX) {
        const overflow = testPointCache.size - TEST_POINT_CACHE_MAX
        let count = 0
        for (const key of testPointCache.keys()) {
          if (count >= overflow) break
          testPointCache.delete(key)
          count++
        }
      }

      testPointTotal.value = apiData.total || 0
      testPointPage.value = page

      if (refreshKey) {
        testPointSelectKey.value++
      }

      if (
        testPointAllIds.value.length < testPointTotal.value &&
        page === 1 &&
        testPointTotal.value <= 200
      ) {
        const allApiData = await testPointApi.getList(formData.project_id as number, {
          page: 1,
          page_size: Math.min(testPointTotal.value, 200),
        })
        if (allApiData?.items) {
          testPointAllIds.value = allApiData.items.map((item: any) => item.id)
        }
      }
    }
  } catch (error) {
    console.error('获取测试点列表失败:', error)
  }
}

// 需求文档/UI原型图选择变化时加载测试点（已合并到watch中，保留供其他地方调用）
const handleSourceFileChange = () => {
  if (!formData.project_id) return
  testPointPage.value = 1
  testPointTotal.value = 0
  testPointAllIds.value = []
  formData.test_point_ids = []
  testPoints.value = []
  testPointCache.clear()
  testPointSelectKey.value++
}

// 全选所有分页的测试点
const selectAllTestPoints = () => {
  if (testPointAllIds.value.length > 0) {
    formData.test_point_ids = [...testPointAllIds.value]
  }
}

// 清空选择
const deselectAllTestPoints = () => {
  formData.test_point_ids = []
}

// 添加测试点（checkbox 勾选时调用，只做添加）
const addTestPoint = (id: number) => {
  if (!formData.test_point_ids.includes(id)) {
    formData.test_point_ids.push(id)
  }
}

// 移除单个测试点
const removeTestPoint = (id: number) => {
  const index = formData.test_point_ids.indexOf(id)
  if (index !== -1) {
    formData.test_point_ids.splice(index, 1)
  }
}

// 获取测试点显示标签
const getTestPointLabel = (id: number) => {
  // 优先从缓存中查找（支持跨页）
  let point = testPointCache.get(id)
  // 如果缓存中没有，从当前页列表中查找
  if (!point) {
    point = testPoints.value.find((p) => p.id === id)
  }
  if (point) {
    return `${point.module} - ${point.function}`
  }
  return `测试点 #${id}`
}

// 选择当前可见的所有测试点
const selectCurrentPageAll = () => {
  const visibleIds = testPoints.value.map((p) => p.id)
  const currentSet = new Set(formData.test_point_ids)
  visibleIds.forEach((id) => {
    if (!currentSet.has(id)) {
      formData.test_point_ids.push(id)
    }
  })
}

// 跳转到指定分页
const goToTestPointPage = async (page: number) => {
  if (isLoadingMore.value) return
  isLoadingMore.value = true
  try {
    await loadTestPoints(page, false, false) // 分页模式：替换数据，不刷新key（保持下拉框打开）
  } finally {
    isLoadingMore.value = false
  }
}

// 获取优先级标签类型
const getPriorityType = (priority: number) => {
  const types: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'info', 4: 'success' }
  return types[priority] || 'info'
}

// 获取已选标签的类型（根据测试点优先级）
const getSelectedTagType = (id: number) => {
  const point = testPointCache.get(id) || testPoints.value.find((p) => p.id === id)
  if (point) {
    return getPriorityType(point.priority)
  }
  return 'primary'
}

// 项目变更
const handleProjectChange = () => {
  formData.requirement_file_ids = []
  formData.ui_file_ids = []
  formData.ui_screen_ids = []
  formData.test_point_ids = []
  contextPreview.value = null
  lastContext.value = {}
  selectedUiPrototypeProjectId.value = ''
  uiPrototypeProjects.value = []
  uiScreens.value = []
  handleSourceFileChange()
  loadProjectFiles()
  loadUIPrototypeProjects()
}

// 项目下拉框获得焦点时加载项目列表
const handleProjectFocus = () => {
  if (!projectsLoaded.value || projects.value.length === 0) {
    getProjects()
  }
}

// 加载 UI 原型项目列表
const loadUIPrototypeProjects = async () => {
  if (!formData.project_id) return
  try {
    const response = await uiPrototypeApi.getUIPrototypeProjectList(formData.project_id as number)
    if (response) {
      uiPrototypeProjects.value = Array.isArray(response)
        ? response
        : (response as any)?.data?.items || []
    }
  } catch (error) {
    console.error('获取 UI 原型项目列表失败:', error)
  }
}

// 加载 UI 原型项目的屏幕列表
const loadUIScreens = async (uiPrototypeProjectId: number) => {
  if (!formData.project_id) return
  try {
    const response = await uiPrototypeApi.getUIScreenList(
      formData.project_id as number,
      uiPrototypeProjectId
    )
    if (response?.data?.items) {
      uiScreens.value = response.data.items.sort(
        (a: any, b: any) => (a.screen_order || 0) - (b.screen_order || 0)
      )
      loadScreenImages()
    }
  } catch (error) {
    console.error('获取 UI 屏幕列表失败:', error)
  }
}

const loadScreenImages = async () => {
  for (const screen of uiScreens.value) {
    if (screen.id && screen.original_file_path && !screenImageUrls.value[screen.id]) {
      try {
        const response: any = await request.get(`/api/v1/file/preview-screen/${screen.id}`, {
          responseType: 'blob',
        })
        // 响应拦截器已经返回了原始响应，我们需要从 response.data 中获取 blob
        const blob =
          response.data instanceof Blob
            ? response.data
            : new Blob([response.data], { type: 'image/jpeg' })
        screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
      } catch (e) {
        console.warn(`加载屏幕图片失败: ${screen.id}`, e)
      }
    }
  }
}

// UI 原型项目选择变化
const handleUIPrototypeProjectChange = async (projectId: number | string) => {
  showParseWarning.value = true
  lastContext.value = {}
  selectedUiPrototypeProjectId.value = projectId as number | ''
  if (projectId) {
    await loadUIScreens(projectId as number)
    if (uiScreens.value.length > 0) {
      formData.ui_screen_ids = uiScreens.value.map((s: any) => s.id)
    } else {
      formData.ui_screen_ids = []
    }
  } else {
    uiScreens.value = []
    formData.ui_screen_ids = []
  }
}

// 提取选中文件的内容
const extractFileContent = async () => {
  if (formData.requirement_file_ids.length === 0 && formData.ui_file_ids.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  const allFileIds = [...formData.requirement_file_ids, ...formData.ui_file_ids]
  fetchingRequirement.value = true
  try {
    const response: ApiResponse = await request.post('/api/v1/file/extract-content', {
      file_ids: allFileIds,
      project_id: Number(formData.project_id),
      force_refresh: true,
    })

    if (response?.code === 200) {
      await loadProjectFiles()
      const data = response.data as { success?: number; failed?: number }
      contextPreview.value = {
        title: `内容提取完成：成功 ${data?.success || 0} 个，失败 ${data?.failed || 0} 个`,
        type: (data?.failed || 0) > 0 ? 'warning' : 'success',
        requirement: `选择了 ${allFileIds.length} 个文件`,
        ui:
          formData.ui_screen_ids.length > 0
            ? `${formData.ui_screen_ids.length} 个屏幕`
            : formData.ui_file_ids.length > 0
              ? `${formData.ui_file_ids.length} 个文件`
              : '',
        uiSpecs: lastContext.value?.ui_specs?.length || 0,
      }
      ElMessage.success('文件内容提取完成')
    } else {
      ElMessage.error(response?.msg || response?.message || '提取内容失败')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '提取内容失败')
  } finally {
    fetchingRequirement.value = false
  }
}

// 跳转到资源管理页面上传文件
const goToResourceManage = () => {
  router.push('/home/requirement')
}

// 步骤导航
const nextStep = () => {
  if (currentStep.value < 2) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const skipToStep2 = () => {
  currentStep.value = 1
}

const validateFlowGraphBeforeGenerate = async () => {
  if (!selectedUiPrototypeProjectId.value || uiScreens.value.length === 0) {
    return true
  }

  const editor = flowSortEditorRef.value as FlowSortEditorExpose | null
  const validation = editor?.getFlowValidationIssues?.()
  if (!validation) return true

  if (validation.errors.length > 0) {
    ElMessage.warning(validation.errors[0])
    return false
  }

  if (validation.warnings.length > 0) {
    try {
      await ElMessageBox.confirm(
        validation.warnings.join('\n'),
        '流程图完整性提示',
        {
          confirmButtonText: '继续生成',
          cancelButtonText: '返回调整',
          type: 'warning',
        }
      )
    } catch {
      return false
    }
  }

  return true
}

// 基于当前用例继续生成（增强版）— 重新生成当前查看的用例
const handleContinueGenerate = async () => {
  const current = viewingCase.value
  if (!current) {
    ElMessage.warning('没有可基于的用例')
    return
  }

  generating.value = true
  progress.value = 0
  progressText.value = '准备重新生成...'

  const progressInterval = setInterval(() => {
    if (progress.value < 90) {
      progress.value += 10
      progressText.value = `生成中... ${progress.value}%`
    }
  }, 500)

  try {
    const apiData = {
      project_id: Number(formData.project_id),
      description: formData.scene || `基于已有用例"${current.title}"继续优化生成`,
      case_type: formData.case_type || current.case_type,
      exec_mode: formData.exec_mode || 'all',
      priority: formData.priority || current.priority || 2,
      enhanced_mode: formData.enhanced_mode !== undefined ? formData.enhanced_mode : true,
      extra_requirements: formData.extra_requirements || '',
      context: {
        base_case: {
          title: current.title,
          module: current.module,
          precondition: current.precondition,
          steps: current.steps || [],
          expected_result: current.expected_result,
        },
        requirement_content: contextPreview.value?.requirement_content || '',
        ui_description: lastContext.value.ui_description || '',
        ui_specs: lastContext.value.ui_specs || [],
        test_points:
          formData.test_point_ids.length > 0 ? [] : contextPreview.value?.test_points || [],
      },
    }

    const response = await caseApi.aiGenerateCaseEnhanced(
      apiData as Parameters<typeof caseApi.aiGenerateCaseEnhanced>[0]
    )
    const caseData = response

    if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
      generatedCases.value[currentCaseIndex.value] = {
        ...generatedCases.value[currentCaseIndex.value],
        title: caseData.title || caseData.name,
        module: caseData.module,
        case_type: caseData.case_type || caseData.type,
        precondition: caseData.precondition,
        test_data: caseData.test_data,
        steps: caseData.steps || [],
        expected_result: caseData.expected_result,
        priority: caseData.priority,
        _error: undefined,
      }
    }

    progress.value = 100
    progressText.value = '生成完成！'
    ElMessage.success('AI继续生成测试用例成功')
  } catch (error: any) {
    console.error('继续生成失败:', error)
    progress.value = 100
    progressText.value = '生成失败'
    const detail = error.response?.data?.detail
    errorMessage.value = detail || error.response?.data?.message || error.message || '继续生成失败'
    generateErrorSuggestions()
    ElMessage.error(errorMessage.value)
  } finally {
    clearInterval(progressInterval)
    generating.value = false
  }
}

// 开始生成（首次）— 每个测试点生成一条用例
const handleGenerate = async () => {
  if (!canGenerate.value) {
    ElMessage.warning('请先选择测试点或需求文档')
    return
  }

  if (!(await validateFlowGraphBeforeGenerate())) {
    return
  }

  const targetPoints =
    formData.test_point_ids.length > 0
      ? formData.test_point_ids
      : (contextPreview.value?.test_points || []).map((tp: any) => tp.id)

  if (targetPoints.length === 0) {
    ElMessage.warning('没有可用的测试点')
    return
  }

  // 数量保护：超过20条时需确认
  const MAX_COUNT = 20
  if (targetPoints.length > MAX_COUNT) {
    try {
      await ElMessageBox.confirm(
        `当前选择了 ${targetPoints.length} 个测试点，将逐个生成用例，可能需要较长时间。是否继续？`,
        '确认生成',
        { confirmButtonText: '继续生成', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }

  generatedCases.value = []
  currentCaseIndex.value = -1
  errorMessage.value = ''
  errorSuggestions.value = []
  generating.value = true
  progress.value = 0
  progressText.value = `准备生成 ${targetPoints.length} 条测试用例...`
  currentStep.value = 2

  const total = targetPoints.length
  let completed = 0

  const progressInterval = setInterval(() => {
    const targetPct = Math.min(90, Math.round((completed / total) * 90))
    if (progress.value < targetPct) {
      progress.value = Math.min(progress.value + 5, targetPct)
      progressText.value = `生成中... ${completed}/${total} (${progress.value}%)`
    }
  }, 300)

  try {
    let context: Record<string, any> = {
      requirement_content: '',
      ui_description: '',
      test_points: [],
      project_config: null,
    }

    if (formData.project_id) {
      const contextResponse: ApiResponse<{
        requirement_content?: string
        ui_descriptions?: unknown[]
        ui_specs?: unknown[]
        test_points?: TestPoint[]
        project_config?: unknown
      }> = await request.post('/api/v1/testCase/generate-context', {
        project_id: Number(formData.project_id),
        requirement_file_ids:
          formData.requirement_file_ids.length > 0 ? formData.requirement_file_ids : undefined,
        ui_file_ids: formData.ui_file_ids.length > 0 ? formData.ui_file_ids : undefined,
        ui_screen_ids: formData.ui_screen_ids.length > 0 ? formData.ui_screen_ids : undefined,
        test_point_ids: targetPoints,
      })

      if (contextResponse?.data) {
        const data = contextResponse.data
        context = {
          requirement_content: data.requirement_content || '',
          ui_description: JSON.stringify(data.ui_descriptions || []),
          ui_specs: data.ui_specs || [],
          test_points: data.test_points || [],
          project_config: data.project_config || null,
        }
        lastContext.value = { ...context }
      }
    }

    const allTestPoints = context.test_points || []

    for (let i = 0; i < targetPoints.length; i++) {
      const tpId = targetPoints[i]
      const tpInfo = allTestPoints.find((tp: TestPoint) => tp.id === tpId)
      const tpLabel = tpInfo ? `${tpInfo.module} - ${tpInfo.function}` : `测试点#${tpId}`

      try {
        const flowSortSubmitData = (flowSortEditorRef.value as FlowSortEditorExpose | null)
          ?.getFlowSortSubmitData?.()
        const apiData: Record<string, any> = {
          project_id: Number(formData.project_id),
          description: formData.scene || `为"${tpLabel}"生成详细测试用例`,
          case_type: formData.case_type,
          exec_mode: formData.exec_mode,
          priority: formData.priority,
          enhanced_mode: formData.enhanced_mode,
          extra_requirements: formData.extra_requirements,
          context: {
            ...context,
            current_test_point: tpInfo || { id: tpId },
            test_point_ids: [tpId],
          },
        }
        apiData.mode = 'graph'
        apiData.flow_sort_data = flowSortSubmitData?.flow_sort_data || {
          nodes: uiScreens.value.map((screen, index) => ({
            screen_id: screen.id,
            screen_order: index + 1,
            flow_type: 'main',
            screen_name: screen.screen_name,
            ui_spec_elements: screen.ui_spec?.elements || [],
            summary: screen.summary || '',
          })),
          edges: [],
          module_info: flowSortModuleInfo.value,
        }
        console.log(
          `[AI生成] 第${i + 1}/${targetPoints.length}条 - tpId:${tpId}, tpLabel:${tpLabel}`
        )
        console.log(`[AI生成] tpInfo详情:`, JSON.stringify(tpInfo, null, 2))
        console.log(
          `[AI生成] apiData.context.current_test_point:`,
          apiData.context.current_test_point
        )

        const response = await caseApi.aiGenerateCaseEnhanced(
          apiData as Parameters<typeof caseApi.aiGenerateCaseEnhanced>[0]
        )
        const caseData = response

        generatedCases.value.push({
          id: Date.now() + i,
          test_point_id: tpId,
          test_point_label: tpLabel,
          title: caseData.title || caseData.name || `${tpLabel} 测试用例`,
          module: caseData.module || tpInfo?.module || '',
          case_type: caseData.case_type || caseData.type || formData.case_type,
          precondition: caseData.precondition || '',
          test_data: caseData.test_data,
          steps: caseData.steps || [],
          expected_result: caseData.expected_result || '',
          priority: caseData.priority || formData.priority,
          scene: formData.scene,
        })
      } catch (err: any) {
        console.error(`生成第${i + 1}条用例失败(${tpLabel}):`, err)
        generatedCases.value.push({
          id: Date.now() + i,
          test_point_id: tpId,
          test_point_label: tpLabel,
          title: `${tpLabel} 测试用例（生成失败）`,
          module: tpInfo?.module || '',
          case_type: formData.case_type,
          precondition: '',
          steps: [],
          expected_result: '',
          priority: formData.priority,
          _error: err.response?.data?.detail || err.message || '生成失败',
          scene: formData.scene,
        })
      }

      completed++
      progress.value = Math.round((completed / total) * 90)
      progressText.value = `生成中... ${completed}/${total}`
    }

    currentCaseIndex.value = 0
    progress.value = 100
    progressText.value = `生成完成！共 ${generatedCases.value.length} 条`
    const failCount = generatedCases.value.filter((c) => c._error).length
    if (failCount === 0) {
      ElMessage.success(`成功生成 ${generatedCases.value.length} 条测试用例`)
    } else {
      ElMessage.warning(
        `生成完成：${generatedCases.value.length - failCount} 成功，${failCount} 失败`
      )
    }
  } catch (error: any) {
    progress.value = 100
    progressText.value = '生成失败'
    errorMessage.value = error.response?.data?.detail || error.message || 'AI生成测试用例失败'
    generateErrorSuggestions()
    ElMessage.error(errorMessage.value)
  } finally {
    clearInterval(progressInterval)
    generating.value = false
  }
}

// 生成错误建议
const generateErrorSuggestions = () => {
  const error = errorMessage.value.toLowerCase()

  // 检测是否是 API Key 相关错误
  if (
    error.includes('认证') ||
    error.includes('authentication') ||
    (error.includes('api') && error.includes('key')) ||
    error.includes('503') ||
    error.includes('无效')
  ) {
    errorSuggestions.value = [
      '请检查 .env 文件中的 DEEPSEEK_API_KEY 是否配置正确',
      '访问 https://platform.deepseek.com/ 获取有效的 API Key',
      '确保 API Key 没有过期或被禁用',
      '如果问题持续，请联系管理员检查 DeepSeek 服务状态',
    ]
    return
  }

  // 检测频率限制错误
  if (
    error.includes('429') ||
    error.includes('rate limit') ||
    error.includes('频率') ||
    error.includes('过多')
  ) {
    errorSuggestions.value = [
      'AI服务请求频率过高，请稍后重试',
      '建议降低请求频率或等待一段时间后再试',
      '可以尝试分批生成测试用例',
    ]
    return
  }

  // 默认错误建议
  errorSuggestions.value = [
    '请确保输入的测试场景描述清晰具体',
    '建议先配置需求文档和UI原型图链接',
    '检查网络连接是否正常',
    '稍后重试，可能是API服务暂时不可用',
    '如果问题持续，请联系管理员',
  ]
}

// 取消生成
const handleCancel = () => {
  ElMessageBox.confirm('确定要取消生成吗？', '取消确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    generating.value = false
    progress.value = 0
    progressText.value = '已取消'
    ElMessage.info('生成已取消')
  })
}

// 保存当前查看的用例（或编辑中的用例）
const handleSaveCase = async () => {
  const caseToSave = isEditingResult.value ? editingCase.value : viewingCase.value
  if (!caseToSave) {
    ElMessage.warning('没有可保存的用例')
    return
  }

  if (caseToSave._error) {
    ElMessage.warning('该用例生成失败，无法保存，请重新生成')
    return
  }

  if (!formData.project_id) {
    ElMessage.warning('请先选择项目')
    return
  }

  saving.value = true
  try {
    const stepsPayload = (caseToSave.steps || []).map((s: any, i: number) => ({
      step: String(s.step || i + 1),
      action: s.action || '',
      param: s.input_value || s.param || '',
      expected_result: s.expected_result || '',
      action_type: s.action_type || '',
      input_value: s.input_value || '',
      target_element: s.target_element || '',
    }))

    const priority = normalizePriority(caseToSave.priority)

    await caseApi.createCase({
      project_id: Number(formData.project_id),
      case_no: generateCaseNo(formData.project_id),
      title: caseToSave.title || '未命名测试用例',
      module: caseToSave.module || '默认模块',
      case_type: caseToSave.case_type || (caseToSave as any).test_category || '',
      precondition: caseToSave.precondition || '系统已通过配置自动登录至目标页面',
      steps:
        stepsPayload.length > 0
          ? stepsPayload
          : [
              {
                step: '1',
                action: '执行测试',
                param: '预期结果正常',
                expected_result: '预期结果正常',
                action_type: 'verify',
                input_value: '',
                target_element: '',
              },
            ],
      expected_result: caseToSave.expected_result || '操作成功',
      priority,
      generate_status: 1,
    } as any)
    ElMessage.success(`"${caseToSave.title}" 保存成功`)
    isEditingResult.value = false

    if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
      generatedCases.value[currentCaseIndex.value]._saved = true
    }
  } catch (error: any) {
    console.error('保存失败:', error)
    const detail = error.response?.data?.detail
    ElMessage.error(detail && typeof detail === 'string' ? detail : '保存失败，请检查必填字段')
  } finally {
    saving.value = false
  }
}

// 开始编辑当前查看的用例
const startEditResult = () => {
  const current = viewingCase.value
  if (!current) return
  editingCase.value = {
    title: current.title || '',
    module: current.module || '',
    case_type: current.case_type || current.test_category || '',
    precondition: current.precondition || '',
    expected_result: current.expected_result || '',
    priority: current.priority || 2,
    steps: current.steps ? JSON.parse(JSON.stringify(current.steps)) : [],
  }
  isEditingResult.value = true
}

// 取消编辑
const cancelEditResult = () => {
  isEditingResult.value = false
}

// 批量保存所有未保存且无错误的用例
const saveAllCases = async () => {
  const toSave = generatedCases.value.filter((c: any) => !c._error && !c._saved)
  if (toSave.length === 0) {
    ElMessage.info('没有需要保存的用例')
    return
  }

  saving.value = true
  let successCount = 0
  let failCount = 0
  let cancelled = false

  for (const c of toSave) {
    if (cancelled) break
    try {
      const stepsPayload = (c.steps || []).map((s: any, i: number) => ({
        step: String(s.step || i + 1),
        action: s.action || '',
        param: s.input_value || s.param || '',
        expected_result: s.expected_result || '',
        action_type: s.action_type || '',
        input_value: s.input_value || '',
        target_element: s.target_element || '',
      }))
      const priority = normalizePriority(c.priority)

      await caseApi.createCase({
        project_id: Number(formData.project_id),
        case_no: generateCaseNo(formData.project_id, c.id),
        title: c.title || '未命名测试用例',
        module: c.module || '默认模块',
        case_type: c.case_type || (c as any).test_category || '',
        precondition: c.precondition || '系统已通过配置自动登录至目标页面',
        steps:
          stepsPayload.length > 0
            ? stepsPayload
            : [
                {
                  step: '1',
                  action: '执行测试',
                  param: '预期结果正常',
                  expected_result: '预期结果正常',
                  action_type: 'verify',
                  input_value: '',
                  target_element: '',
                },
              ],
        expected_result: c.expected_result || '操作成功',
        priority,
        generate_status: 1,
      } as any)
      c._saved = true
      successCount++
    } catch (e: any) {
      console.error(`保存失败(${c.title}):`, e)
      failCount++
    }
  }

  saving.value = false
  if (cancelled) {
    ElMessage.info(`已取消，成功保存 ${successCount} 条`)
  } else if (failCount === 0) {
    ElMessage.success(`全部保存成功，共 ${successCount} 条`)
  } else {
    ElMessage.warning(`保存完成：${successCount} 成功，${failCount} 失败`)
  }
}

// 添加步骤（编辑模式）
const addEditStep = () => {
  editingCase.value.steps.push({
    step: editingCase.value.steps.length + 1,
    action: '',
    param: '',
    expected_result: '',
    test_data: {},
  })
}

// 删除步骤（编辑模式）
const removeEditStep = (index: number) => {
  if (editingCase.value.steps.length > 1) {
    editingCase.value.steps.splice(index, 1)
    editingCase.value.steps.forEach((s: any, i: number) => {
      s.step = i + 1
    })
  }
}

// 重试
const handleRetry = () => {
  errorMessage.value = ''
  errorSuggestions.value = []
  handleGenerate()
}

// 重置表单
const resetForm = () => {
  formData.scene = ''
  formData.case_type = ''
  formData.exec_mode = 'all'
  formData.priority = 2
  formData.extra_requirements = ''
  formData.enhanced_mode = true
  generatedCases.value = []
  currentCaseIndex.value = -1
  errorMessage.value = ''
  errorSuggestions.value = []
  isEditingResult.value = false
  currentStep.value = 0
}

// 返回
const handleBack = () => {
  router.push('/home/case')
}

// 辅助方法
const getTypeTagType = (type: string) => {
  const typeMap: Record<string, string> = {
    ui_automation: 'success',
    manual: 'info',
    api_automation: '',
    performance: 'warning',
    security: 'danger',
    UI: 'success',
    API: '',
    功能: 'info',
    功能测试: 'info',
    functional: 'info',
  }
  return typeMap[type] || 'info'
}

const getTypeLabel = (type: string) => {
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
    接口: 'API自动化',
    接口测试: 'API自动化',
  }
  return typeMap[type] || type
}

const getPriorityTagType = (priority: any) => {
  const priorityMap: Record<string, string> = {
    '1': 'danger',
    P0: 'danger',
    '2': 'warning',
    P2: 'warning',
    '3': 'info',
    P3: 'info',
  }
  return priorityMap[String(priority)] || 'info'
}

const getPriorityLabel = (priority: any) => {
  const priorityMap: Record<string, string> = {
    '1': '高(P0)',
    P0: 'P0-高',
    '2': '中(P2)',
    P2: 'P2-中',
    '3': '低(P3)',
    P3: 'P3-低',
  }
  return priorityMap[String(priority)] || priority
}

const getDataTypeLabel = (key: string | number) => {
  const keyStr = String(key)
  const labelMap: Record<string, string> = {
    normal: '正向数据',
    boundary: '边界值',
    abnormal: '异常数据',
  }
  return labelMap[keyStr] || keyStr
}

// 清理预期结果中的步骤编号标记（如【1】【2】等）
const cleanExpectedResult = (text: string): string => {
  if (!text) return text
  // 移除开头的步骤编号标记，如【1】【2】等
  return text.replace(/^【\d+】\s*/, '')
}

// 初始化
onMounted(async () => {
  const projectId = route.query.project_id
  if (projectId) {
    formData.project_id = Number(projectId)
  }

  const fids = route.query.requirement_file_ids
  if (fids) {
    try {
      const parsed = JSON.parse(String(fids))
      if (Array.isArray(parsed)) {
        formData.requirement_file_ids = parsed.map(Number).filter((n) => !Number.isNaN(n))
      }
    } catch {
      /* ignore */
    }
  }

  const singleFid = route.query.file_id
  if (!formData.requirement_file_ids.length && singleFid) {
    const id = Number(singleFid)
    if (!Number.isNaN(id) && id > 0) {
      formData.requirement_file_ids = [id]
    }
  }

  // 从测试点提取页面跳转时，预选测试点
  const tpIds = route.query.test_point_ids
  if (tpIds) {
    try {
      const parsed = JSON.parse(String(tpIds))
      if (Array.isArray(parsed)) {
        formData.test_point_ids = parsed.map(Number).filter((n) => !Number.isNaN(n) && n > 0)
      }
    } catch {
      /* ignore */
    }
  }

  await getProjects()
  if (formData.project_id) {
    await loadProjectFiles()
    await loadUIPrototypeProjects()

    if (formData.requirement_file_ids.length > 0) {
      await loadTestPoints(1)
    }
  }
})

// 监听需求文档/UI原型图选择变化，自动加载测试点
watch(
  [() => formData.requirement_file_ids, () => formData.ui_file_ids],
  async ([newReqIds, newUiIds], [oldReqIds, oldUiIds]) => {
    const reqChanged = JSON.stringify(newReqIds || []) !== JSON.stringify(oldReqIds || [])
    const uiChanged = JSON.stringify(newUiIds || []) !== JSON.stringify(oldUiIds || [])

    if ((reqChanged || uiChanged) && formData.project_id) {
      handleSourceFileChange()
      if ((newReqIds && newReqIds.length > 0) || (newUiIds && newUiIds.length > 0)) {
        await loadTestPoints(1)
      }
    }
  },
  { deep: true }
)

onUnmounted(() => {
  generating.value = false
  progress.value = 0
  errorMessage.value = ''
  generatedCases.value = []
  currentCaseIndex.value = -1
  Object.values(screenImageUrls.value).forEach((url) => {
    if (url.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  })
  screenImageUrls.value = {}
})
</script>

<style scoped>
.ai-generate-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.steps-indicator {
  margin-bottom: 30px;
}

.step-card,
.progress-card,
.result-card,
.error-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.context-preview {
  max-width: 800px;
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
  margin-top: 30px;
  text-align: center;
  padding-top: 20px;
  border-top: 1px solid #eee;
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

.result-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.edit-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;

  .edit-field {
    label {
      display: block;
      font-size: 13px;
      color: #606266;
      margin-bottom: 6px;
      font-weight: 500;
    }

    &.full-width {
      grid-column: 1 / -1;
    }
  }
}

.editable-steps-list {
  .editable-step-card {
    background: #fafbfc;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;

    .step-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .step-num {
        font-weight: 600;
        color: #409eff;
        font-size: 14px;
      }
    }

    .step-card-body {
      .step-edit-field {
        margin-bottom: 10px;

        label {
          display: block;
          font-size: 12px;
          color: #606266;
          margin-bottom: 4px;
          font-weight: 500;
        }
      }
    }
  }

  .empty-steps-hint {
    text-align: center;
    padding: 20px;
    color: #909399;
  }
}

/* ========== 拖拽排序样式 ========== */
.ui-file-sortable-list {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 8px;
  background: #fafafa;
}

.sortable-file-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 6px;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  cursor: grab;
  transition: all 0.2s ease;
}

.sortable-file-item:last-child {
  margin-bottom: 0;
}

.sortable-file-item:hover {
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
  border-color: #409eff;
}

.sortable-file-item.is-dragging {
  opacity: 0.5;
  border-style: dashed;
  border-color: #409eff;
  background: #ecf5ff;
}

.drag-handle {
  color: #c0c4cc;
  font-size: 16px;
  cursor: grab;
  margin-right: 12px;
  user-select: none;
}

.sort-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409eff;
  color: white;
  font-size: 12px;
  font-weight: bold;
  margin-right: 12px;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

/* ========== UI 原型图版本选择样式 ========== */
.ui-mockup-section {
  width: 100%;
}

.version-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.version-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.version-name {
  flex: 1;
}

.screen-preview-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.04) 0%, rgba(15, 23, 42, 0.55) 100%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.screen-image-wrapper:hover .screen-preview-overlay {
  opacity: 1;
}

/* ========== UI 屏幕样式 ========== */
.screen-preview-form-item :deep(.el-form-item__content) {
  width: 100%;
  min-height: 0;
  display: block;
}

.screen-preview-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
  border: 1px solid #ebeef5;
  box-sizing: border-box;
}

.screen-preview-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 4px;
}

.preview-overview-main {
  flex: 1;
  min-width: 0;
}

.preview-overview-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.preview-overview-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.preview-overview-desc {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.preview-overview-tips {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.preview-tip-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #606266;
  font-size: 12px;
  white-space: nowrap;
}

.screen-sort-editor {
  min-height: clamp(460px, 62vh, 760px);
}

.ui-screens-empty {
  width: 100%;
  padding: 40px 0;
  border: 1px dashed #dcdfe6;
  border-radius: 12px;
  background: #fafbfc;
}

@media (max-width: 1200px) {
  .screen-preview-overview {
    flex-direction: column;
  }

  .preview-overview-tips {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .screen-preview-wrapper {
    padding: 12px;
    border-radius: 12px;
  }

  .screen-sort-editor {
    min-height: 420px;
  }
}

/* ========== 测试点选择器 ========== */
.test-point-selector {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #fff;
  overflow: hidden;
}

.tp-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: #f8f9fb;
  border-bottom: 1px solid #ebeef5;
}

.tp-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #606266;
}

.tp-toolbar-left strong {
  color: #303133;
}

.tp-toolbar-right {
  display: flex;
  gap: 4px;
}

.tp-select {
  width: 100%;
}

.tp-select :deep(.el-input__wrapper) {
  border-radius: 0;
  box-shadow: none !important;
  padding: 4px 12px;
  background: #fafbfc;
}

.tp-select :deep(.el-input__wrapper:hover) {
  background: #f0f2f5;
}

.tp-select :deep(.el-input__wrapper.is-focus) {
  box-shadow: none !important;
  background: #fff;
}

.tp-chips {
  padding: 10px 14px;
  background: #f8f9fb;
  border-top: 1px solid #ebeef5;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>

<!-- 下拉框全局样式 -->
<style>
.tp-dropdown {
  border-radius: 8px !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1) !important;
  border: 1px solid #dcdfe6 !important;
}

.tp-d-header {
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.tp-d-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  margin-bottom: 10px;
  transition: all 0.2s;
}

.tp-d-search:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.tp-d-search input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  width: 100%;
  color: #606266;
}

.tp-d-search input::placeholder {
  color: #c0c4cc;
}

.tp-d-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

/* 选项 */
.tp-dropdown .el-select-dropdown__item {
  padding: 0 !important;
  height: auto !important;
  line-height: normal !important;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.15s;
}

.tp-dropdown .el-select-dropdown__item:last-child {
  border-bottom: none;
}

.tp-dropdown .el-select-dropdown__item.is-hovering,
.tp-dropdown .el-select-dropdown__item:hover {
  background-color: #f5faff !important;
}

.tp-dropdown .el-select-dropdown__item.is-checked {
  background-color: #ecf5ff !important;
}

.tp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}

.tp-check input[type='checkbox'] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #409eff;
  flex-shrink: 0;
}

.tp-content {
  flex: 1;
  min-width: 0;
}

.tp-row1 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.tp-mod {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.tp-sep {
  color: #c0c4cc;
  font-size: 11px;
}

.tp-func {
  font-size: 13px;
  font-weight: 500;
  color: #409eff;
}

.tp-pri {
  margin-left: auto;
  flex-shrink: 0;
}

.tp-row2 {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}

/* 底部分页 */
.tp-d-footer {
  padding: 10px 16px;
  text-align: center;
  border-top: 1px solid #ebeef5;
  background: #fafafa;
}

.tp-d-footer .el-pagination {
  justify-content: center;
}
.tp-d-footer .el-pagination .el-pager li {
  min-width: 28px;
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  border-radius: 4px;
  margin: 0 2px;
}
.tp-d-footer .el-pagination .el-pager li.is-active {
  background: #409eff;
  color: #fff;
}
.tp-d-footer .el-pagination .btn-prev,
.tp-d-footer .el-pagination .btn-next {
  min-width: 28px;
  height: 28px;
  border-radius: 4px;
}

/* 空状态 */
.tp-empty {
  padding: 32px 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
