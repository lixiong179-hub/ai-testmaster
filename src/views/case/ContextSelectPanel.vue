<template>
  <el-card class="step-card">
    <template #header>
      <div class="card-header">
        <span>选择需求来源</span>
        <el-tag type="info">可选步骤，不选择则使用手动输入</el-tag>
      </div>
    </template>

    <el-form label-width="120px">
      <!-- 项目选择 -->
      <el-form-item label="项目">
        <el-select
          v-model="store.formData.project_id"
          placeholder="请选择项目"
          style="width: 400px"
          filterable
          :loading="store.projectsLoading"
          @change="store.handleProjectChange"
          @focus="store.handleProjectFocus"
        >
          <el-option
            v-for="project in store.projects"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>
      </el-form-item>

      <!-- 需求文档选择 -->
      <el-form-item label="需求文档">
        <el-select
          v-model="store.formData.requirement_file_ids"
          multiple
          placeholder="选择需求文档（可多选）"
          style="width: 600px"
          collapse-tags
          collapse-tags-tooltip
        >
          <el-option
            v-for="file in store.requirementFiles"
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
          @click="store.extractFileContent"
          :loading="fetchingRequirement"
          style="margin-left: 10px"
        >
          提取内容
        </el-button>
        <el-button
          type="success"
          plain
          size="small"
          @click="$emit('go-resource-manage')"
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
              v-model="store.selectedUiPrototypeProjectId"
              placeholder="请选择UI原型图版本"
              style="width: 100%"
              @change="store.handleUIPrototypeProjectChange"
              :disabled="!store.formData.project_id"
              clearable
            >
              <el-option
                v-for="project in store.uiPrototypeProjects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              >
                <div class="version-option">
                  <span class="version-name">{{ project.name }}</span>
                  <el-tag v-if="project.parse_status === 'completed'" type="success" size="small">
                    已解析
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
                    解析失败
                  </el-tag>
                  <el-tag v-else type="info" size="small"> 待解析 </el-tag>
                </div>
              </el-option>
            </el-select>
            <el-button
              type="primary"
              plain
              @click="store.loadUIPrototypeProjects"
              :disabled="!store.formData.project_id"
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
        v-if="store.selectedUiPrototypeProjectId"
        class="screen-preview-form-item"
      >
        <el-alert
          v-if="
            store.selectedUiPrototypeProject &&
            store.selectedUiPrototypeProject.parse_status !== 'completed' &&
            store.showParseWarning
          "
          :title="
            store.selectedUiPrototypeProject.parse_status === 'partial'
              ? `该UI原型图部分解析（${store.selectedUiPrototypeProject.parsed_count}/${store.selectedUiPrototypeProject.screen_count}），未解析的屏幕将无法获取详细元素信息`
              : '该UI原型图尚未解析，将无法获取详细的按钮、输入框等元素信息，建议先在资源管理中进行解析'
          "
          type="warning"
          show-icon
          closable
          style="margin-bottom: 16px"
          @close="store.showParseWarning = false"
        />
        <div v-if="store.uiScreens.length > 0" class="screen-preview-wrapper">
          <div class="screen-preview-overview">
            <div class="preview-overview-main">
              <div class="preview-overview-title">
                <span class="preview-overview-name">{{
                  store.selectedUiPrototypeProject?.name || '当前UI版本'
                }}</span>
                <el-tag size="small" type="info" effect="plain"
                  >共 {{ store.uiScreens.length }} 个屏幕</el-tag
                >
                <el-tag size="small" :type="store.screenPreviewStatusType" effect="plain">
                  {{ store.screenPreviewStatusText }}
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
            :screens="store.uiScreens"
            :screen-image-urls="store.screenImageUrls"
            :module-info="store.flowSortModuleInfo"
            @update:sort-data="store.handleFlowSortUpdate"
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
        <div class="test-point-selector" :class="{ 'has-data': store.testPointTotal > 0 }">
          <!-- 头部工具栏 -->
          <div
            class="tp-toolbar"
            v-if="store.testPointTotal > 0 || store.formData.test_point_ids.length > 0"
          >
            <div class="tp-toolbar-left">
              <span class="tp-stat" v-if="store.testPointTotal > 0"
                >共 <strong>{{ store.testPointTotal }}</strong> 条</span
              >
              <el-tag
                size="small"
                type="primary"
                effect="dark"
                v-if="store.formData.test_point_ids.length > 0"
              >
                已选 {{ store.formData.test_point_ids.length }}
              </el-tag>
            </div>
            <div class="tp-toolbar-right">
              <el-button
                link
                type="primary"
                size="small"
                @mousedown.prevent
                @click.stop.prevent="store.selectAllTestPoints"
                :disabled="store.testPointAllIds.length === 0"
              >
                全选
              </el-button>
              <el-button
                link
                type="danger"
                size="small"
                @mousedown.prevent
                @click.stop.prevent="store.deselectAllTestPoints"
                :disabled="store.formData.test_point_ids.length === 0"
              >
                清空
              </el-button>
            </div>
          </div>

          <!-- 选择器 -->
          <el-select
            :key="store.testPointSelectKey"
            v-model="store.formData.test_point_ids"
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
                    >{{ store.testPointPage }}/{{
                      Math.ceil(store.testPointTotal / store.testPointPageSize) || 1
                    }}</span
                  >
                  <el-button
                    link
                    size="small"
                    type="primary"
                    @mousedown.prevent
                    @click.stop.prevent="store.selectCurrentPageAll"
                  >
                    本页全选
                  </el-button>
                </div>
              </div>
            </template>

            <!-- 选项列表 -->
            <el-option
              v-for="point in store.testPoints"
              :key="point.id"
              :label="`${point.module} - ${point.point}`"
              :value="point.id"
              :class="{ 'is-checked': store.formData.test_point_ids.includes(point.id) }"
              @click.stop
            >
              <div class="tp-item" @mousedown.prevent @click.stop>
                <label class="tp-check" @mousedown.prevent @click.stop>
                  <input
                    type="checkbox"
                    :checked="store.formData.test_point_ids.includes(point.id)"
                    @click.stop
                    @change="
                      (e: Event) => {
                        ;(e.target as HTMLInputElement).checked
                          ? store.addTestPoint(point.id)
                          : store.removeTestPoint(point.id)
                      }
                    "
                  />
                </label>
                <div class="tp-content">
                  <div class="tp-row1">
                    <span class="tp-mod">{{ point.module }}</span>
                    <span class="tp-sep">/</span>
                    <span class="tp-point">{{ point.point }}</span>
                    <el-tag
                      size="small"
                      :type="store.getPriorityType(point.priority)"
                      round
                      class="tp-pri"
                    >
                      {{ store.getPriorityLabel(point.priority) }}
                    </el-tag>
                  </div>
                  <div class="tp-row2">{{ point.point }}</div>
                </div>
              </div>
            </el-option>

            <!-- 底部分页 -->
            <template #footer v-if="store.testPointTotal > 0">
              <div class="tp-d-footer" @mousedown.prevent>
                <el-pagination
                  :current-page="store.testPointPage"
                  :page-size="store.testPointPageSize"
                  :total="store.testPointTotal"
                  layout="prev, pager, next, jumper"
                  size="small"
                  @current-change="store.goToTestPointPage"
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
            <div class="tp-chips" v-if="store.formData.test_point_ids.length > 0">
              <el-tag
                v-for="id in store.formData.test_point_ids.slice(0, 6)"
                :key="id"
                closable
                effect="dark"
                :type="store.getSelectedTagType(id)"
                size="small"
                @close="store.removeTestPoint(id)"
                >{{ store.getTestPointLabel(id) }}</el-tag
              >
              <el-popover
                v-if="store.formData.test_point_ids.length > 6"
                placement="bottom-start"
                :width="280"
                trigger="hover"
              >
                <template #reference>
                  <el-tag effect="dark" type="info" round size="small"
                    >+{{ store.formData.test_point_ids.length - 6 }}</el-tag
                  >
                </template>
                <div style="max-height: 200px; overflow-y: auto; padding: 4px 0">
                  <el-tag
                    v-for="id in store.formData.test_point_ids.slice(6)"
                    :key="id"
                    closable
                    effect="dark"
                    :type="store.getSelectedTagType(id)"
                    size="small"
                    style="margin: 2px"
                    @close="store.removeTestPoint(id)"
                  >
                    {{ store.getTestPointLabel(id) }}
                  </el-tag>
                </div>
              </el-popover>
            </div>
          </transition>
        </div>
      </el-form-item>

      <!-- 已选择的上下文信息展示 -->
      <el-form-item label="上下文预览" v-if="store.contextPreview">
        <div class="context-preview">
          <el-alert
            :title="store.contextPreview.title"
            :type="store.contextPreview.type"
            show-icon
            :closable="false"
          >
            <template #default>
              <div v-if="store.contextPreview.requirement">
                需求文档: {{ store.contextPreview.requirement }}
              </div>
              <div v-if="store.contextPreview.ui">UI原型: {{ store.contextPreview.ui }}</div>
              <div v-if="store.contextPreview.uiSpecs">
                已解析UI规格: {{ store.contextPreview.uiSpecs }}个页面
              </div>
              <div v-if="store.contextPreview.test_points">
                测试点: {{ store.contextPreview.test_points?.length || 0 }}
              </div>
            </template>
          </el-alert>
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="$emit('next')">
          下一步：配置测试参数
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button @click="$emit('skip-to-step2')">跳过，直接手动输入</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Refresh, Search, Rank, View } from '@element-plus/icons-vue'
import FlowSortEditor from '@/components/case/FlowSortEditor.vue'
import { useGenerateStore } from '@/store/useGenerateStore'

const store = useGenerateStore()
const fetchingRequirement = ref(false)

type FlowSortValidationResult = {
    errors: string[]
    warnings: string[]
}

type FlowSortEditorExpose = InstanceType<typeof FlowSortEditor> & {
    getFlowSortSubmitData?: () => { mode: 'graph'; flow_sort_data: Record<string, unknown> }
    getFlowValidationIssues?: () => FlowSortValidationResult
}

const flowSortEditorRef = ref<InstanceType<typeof FlowSortEditor> | null>(null)

/** 暴露 FlowSortEditor 引用供父组件获取 */
function getFlowSortEditorRef(): FlowSortEditorExpose | null {
    return flowSortEditorRef.value as FlowSortEditorExpose | null
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
    const screen = store.uiScreens.find((s) => s.id === screenData.screen_id)
    if (screen && store.screenImageUrls[screen.id]) {
        // 由父组件处理图片预览
        emitPreviewScreen(store.screenImageUrls[screen.id])
    }
}

const emit = defineEmits<{
    'next': []
    'skip-to-step2': []
    'go-resource-manage': []
    'preview-screen': [url: string]
}>()

function emitPreviewScreen(url: string) {
    emit('preview-screen', url)
}

defineExpose({ getFlowSortEditorRef })
</script>

<style scoped>
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

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

.context-preview {
    max-width: 800px;
}

/* 测试点选择器 */
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
</style>
