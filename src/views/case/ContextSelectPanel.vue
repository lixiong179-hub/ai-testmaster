<template>
  <el-card class="step-card">
    <template #header>
      <div class="card-header">
        <span>选择需求来源</span>
        <el-tag type="info">可选步骤，不选择则使用手动输入</el-tag>
      </div>
    </template>
    <el-form label-width="120px">
      <el-form-item label="项目">
        <el-select v-model="store.formData.project_id" placeholder="请选择项目" style="width: 400px" filterable :loading="store.projectsLoading" @change="store.handleProjectChange" @focus="store.handleProjectFocus">
          <el-option v-for="project in store.projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="需求文档">
        <el-select v-model="store.formData.requirement_file_ids" multiple placeholder="选择需求文档（可多选）" style="width: 600px" collapse-tags collapse-tags-tooltip>
          <el-option v-for="file in store.requirementFiles" :key="file.id" :label="file.file_name" :value="file.id">
            <span>{{ file.file_name }}</span>
            <el-tag size="small" type="primary" style="margin-left: 8px">{{ file.extract_status === 'completed' ? '已提取' : file.extract_status }}</el-tag>
          </el-option>
        </el-select>
        <el-button type="primary" plain size="small" @click="store.extractFileContent" :loading="fetchingRequirement" style="margin-left: 10px">提取内容</el-button>
        <el-button type="success" plain size="small" @click="$emit('go-resource-manage')" style="margin-left: 10px">上传文件</el-button>
      </el-form-item>
      <el-form-item label="UI原型图">
        <div class="ui-mockup-section">
          <el-alert title="选择UI原型图版本（可选）" type="info" :closable="false" show-icon style="margin-bottom: 16px">
            <template #default>选择不同版本的UI原型图，下方可查看和调整屏幕顺序。 点击图片可预览大图。</template>
          </el-alert>
          <div class="version-selector">
            <el-select v-model="store.selectedUiPrototypeProjectId" placeholder="请选择UI原型图版本" style="width: 100%" @change="store.handleUIPrototypeProjectChange" :disabled="!store.formData.project_id" clearable>
              <el-option v-for="project in store.uiPrototypeProjects" :key="project.id" :label="project.name" :value="project.id">
                <div class="version-option">
                  <span class="version-name">{{ project.name }}</span>
                  <el-tag v-if="project.parse_status === 'completed'" type="success" size="small">已解析</el-tag>
                  <el-tag v-else-if="project.parse_status === 'partial'" type="warning" size="small">部分解析 ({{ project.parsed_count }}/{{ project.screen_count }})</el-tag>
                  <el-tag v-else-if="project.parse_status === 'failed'" type="danger" size="small">解析失败</el-tag>
                  <el-tag v-else type="info" size="small">待解析</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-button type="primary" plain @click="store.loadUIPrototypeProjects" :disabled="!store.formData.project_id" style="margin-left: 12px"><el-icon><Refresh /></el-icon>刷新</el-button>
          </div>
        </div>
      </el-form-item>
      <ContextHistoryCases />
      <ContextScreenPreview ref="screenPreviewRef" @preview-screen="(url: string) => emit('preview-screen', url)" @test-point-link="handleTestPointLinkResult" />
      <ContextTestPointSelector :related-test-point-ids="relatedTestPointIds" />
      <el-form-item label="上下文预览" v-if="store.contextPreview">
        <div class="context-preview">
          <el-alert :title="store.contextPreview.title" :type="store.contextPreview.type" show-icon :closable="false">
            <template #default>
              <div v-if="store.contextPreview.requirement">需求文档: {{ store.contextPreview.requirement }}</div>
              <div v-if="store.contextPreview.ui">UI原型: {{ store.contextPreview.ui }}</div>
              <div v-if="store.contextPreview.uiSpecs">已解析UI规格: {{ store.contextPreview.uiSpecs }}个页面</div>
              <div v-if="store.contextPreview.test_points">测试点: {{ store.contextPreview.test_points?.length || 0 }}</div>
            </template>
          </el-alert>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="$emit('next')">下一步：配置测试参数<el-icon><ArrowRight /></el-icon></el-button>
        <el-button @click="$emit('skip-to-step2')">跳过，直接手动输入</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight, Refresh } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import ContextHistoryCases from './components/ContextHistoryCases.vue'
import ContextScreenPreview from './components/ContextScreenPreview.vue'
import ContextTestPointSelector from './components/ContextTestPointSelector.vue'

const store = useGenerateStore()
const fetchingRequirement = ref(false)
const relatedTestPointIds = ref<number[]>([])
const screenPreviewRef = ref<InstanceType<typeof ContextScreenPreview> | null>(null)

const emit = defineEmits<{ next: []; 'skip-to-step2': []; 'go-resource-manage': []; 'preview-screen': [url: string] }>()

const handleTestPointLinkResult = (ids: number[]) => { relatedTestPointIds.value = ids }

function getFlowSortEditorRef() { return screenPreviewRef.value?.getFlowSortEditorRef?.() ?? null }

defineExpose({ getFlowSortEditorRef })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.ui-mockup-section { width: 100%; }
.version-selector { display: flex; align-items: center; gap: 12px; }
.version-option { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.version-name { flex: 1; }
.context-preview { max-width: 800px; }
</style>
