<template>
  <div class="resource-manage-container">
    <el-card class="filter-card">
      <el-form :inline="true" :model="resourceList.filterForm">
        <el-form-item label="项目">
          <el-select
            v-model="resourceList.filterForm.project_id"
            placeholder="请先选择项目"
            style="width: 200px"
            clearable
            filterable
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="resourceList.filterForm.resource_type"
            placeholder="全部"
            style="width: 150px"
            clearable
            @change="resourceList.handleSearch"
          >
            <el-option
              v-for="option in RESOURCE_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="resourceList.handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="main-content">
      <div class="iteration-panel">
        <div class="iteration-panel-header">
          <span class="panel-title">迭代版本</span>
          <el-button
            type="primary"
            size="small"
            @click="handleAddIterationWrapper"
            :disabled="!resourceList.filterForm.project_id"
          >
            <el-icon><Plus /></el-icon>
            新建迭代
          </el-button>
        </div>

        <div class="iteration-list" v-if="resourceList.filterForm.project_id">
          <div
            class="iteration-card"
            :class="{ active: iterationManager.selectedIterationId === null }"
            @click="handleSelectIterationAndRefresh(null)"
          >
            <div class="iteration-card-info">
              <span class="iteration-name">全部</span>
            </div>
          </div>

          <!-- 迭代列表：仅当有数据时渲染 -->
          <template
            v-for="(iteration, index) in safeIterationsArray"
            :key="'panel-' + (iteration?.id ?? index)"
          >
            <div
              v-if="iteration && iteration.id"
              class="iteration-card"
              :class="{ active: iterationManager.selectedIterationId === iteration.id }"
              @click="handleSelectIterationAndRefresh(iteration.id)"
            >
              <div class="iteration-card-info">
                <div class="iteration-name-row">
                  <span class="iteration-name" :title="iteration?.name">{{ iteration?.name }}</span>
                  <el-tag size="small" class="version-tag">{{ iteration?.version }}</el-tag>
                </div>

                <div class="iteration-stats" v-if="iteration && iteration.id">
                  <span
                    class="stat-item"
                    v-if="
                      getIterationStats(iteration.id).files > 0 ||
                      getIterationStats(iteration.id).prototypes > 0
                    "
                  >
                    <el-icon><Document /></el-icon>
                    {{ getIterationStats(iteration.id).files }} 个文档
                  </span>
                  <span class="stat-item" v-if="getIterationStats(iteration.id).prototypes > 0">
                    <el-icon><Picture /></el-icon>
                    {{ getIterationStats(iteration.id).prototypes }} 个原型
                  </span>
                </div>

                <div class="iteration-meta">
                  <el-tag
                    :type="iterationManager.getIterationStatusType(iteration?.status)"
                    size="small"
                  >
                    {{ iterationManager.getIterationStatusText(iteration?.status) }}
                  </el-tag>
                  <span @click.stop>
                    <el-dropdown
                      trigger="click"
                      @command="
                        (cmd: string) => iteration && handleIterationCommandWrapper(cmd, iteration)
                      "
                    >
                      <el-icon class="more-icon"><MoreFilled /></el-icon>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="edit">编辑</el-dropdown-item>
                          <el-dropdown-item command="delete">删除</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </span>
                </div>
              </div>
            </div>
          </template>

          <div
            class="iteration-card"
            :class="{ active: iterationManager.selectedIterationId === 0 }"
            @click="handleSelectIterationAndRefresh(0)"
          >
            <div class="iteration-card-info">
              <div class="iteration-name-row">
                <span class="iteration-name">未分类</span>
                <el-tag size="small" type="info" class="version-tag">无迭代</el-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="iteration-empty" v-if="!resourceList.filterForm.project_id">
          <el-icon :size="40" color="#c0c4cc"><FolderOpened /></el-icon>
          <p class="empty-text">请先选择一个项目</p>
          <p class="empty-hint">选择项目后将显示迭代列表</p>
        </div>

        <div class="iteration-empty" v-else-if="safeIterationsArray.length === 0">
          <el-icon :size="40" color="#c0c4cc"><Plus /></el-icon>
          <p class="empty-text">该项目暂无迭代</p>
          <p class="empty-hint">创建迭代以更好地组织和管理您的需求文档</p>
          <el-button
            type="primary"
            size="small"
            @click="handleAddIterationWrapper"
            style="margin-top: 12px"
          >
            <el-icon><Plus /></el-icon>
            创建第一个迭代
          </el-button>
        </div>
      </div>

      <div class="resource-area">
        <el-card class="list-card">
          <template #header>
            <div class="resource-header">
              <span class="resource-title">{{ iterationManager.getCurrentIterationTitle() }}</span>
              <div class="resource-actions">
                <el-button
                  type="success"
                  @click="handleAddFileWrapper"
                  :disabled="!resourceList.filterForm.project_id"
                >
                  <el-icon><Upload /></el-icon>
                  上传文件
                </el-button>
              </div>
            </div>
          </template>
          <el-table
            :data="resourceList.resources"
            style="width: 100%"
            v-loading="resourceList.isLoading"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="资源名称" min-width="200">
              <template #default="{ row }">
                <div class="resource-name-cell">
                  <el-link
                    v-if="row.resource_type === 'ui_mockup'"
                    type="primary"
                    underline="never"
                    @click="handleEditWrapper(row)"
                  >
                    {{ row.name }}
                  </el-link>
                  <el-link
                    v-else-if="row.source_type === 'file' && row.id"
                    type="primary"
                    :href="`/api/v1/file/preview/${row.id}`"
                    target="_blank"
                    underline="never"
                  >
                    {{ row.name }}
                  </el-link>
                  <span v-else>{{ row.name }}</span>
                  <el-tag
                    v-if="row.resource_type === 'ui_mockup' && row.screen_count"
                    size="small"
                    type="info"
                    class="screen-count-tag"
                  >
                    {{ row.screen_count }}张图片
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="resource_type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="resourceList.getResourceTypeTagType(row.resource_type)">
                  {{ resourceList.getResourceTypeLabel(row.resource_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="upload_time" label="上传时间" width="180">
              <template #default="{ row }">
                {{ row.upload_time || row.created_at || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  size="small"
                  @click="resourceOperations.handleAnalyze(row)"
                  >AI分析</el-button
                >
                <el-button type="info" size="small" @click="handleEditWrapper(row)">
                  {{ row.resource_type === 'ui_mockup' ? '查看' : '编辑' }}
                </el-button>
                <el-button type="danger" size="small" @click="resourceOperations.handleDelete(row)"
                  >删除</el-button
                >
              </template>
            </el-table-column>
          </el-table>

          <div
            class="empty-resources"
            v-if="!resourceList.isLoading && resourceList.resources.length === 0"
          >
            <el-icon :size="60" color="#d0d5dd"><Files /></el-icon>
            <p class="empty-title">暂无资源</p>
            <p class="empty-desc">该迭代下还没有上传任何资源</p>
            <el-button type="primary" @click="handleAddFileWrapper">
              <el-icon><Upload /></el-icon>
              上传第一个文件
            </el-button>
          </div>

          <div class="pagination" v-if="resourceList.total > 0">
            <el-pagination
              v-model:current-page="resourceList.pagination.page"
              v-model:page-size="resourceList.pagination.pageSize"
              :page-sizes="RESOURCE_CONFIG.PAGE_SIZE_OPTIONS"
              layout="total, sizes, prev, pager, next, jumper"
              :total="resourceList.total"
              @size-change="resourceList.handleSizeChange"
              @current-change="resourceList.handleCurrentChange"
            />
          </div>
        </el-card>
      </div>
    </div>

    <!-- 文件上传/编辑弹窗 -->
    <el-dialog
      v-model="resourceUpload.fileDialogVisible"
      :title="resourceUpload.fileDialogTitle"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="fileFormLocalRef"
        :model="resourceUpload.fileFormData"
        :rules="resourceUpload.fileFormRules"
        label-width="120px"
      >
        <el-form-item label="项目" prop="project_id">
          <el-select
            v-model="resourceUpload.fileFormData.project_id"
            placeholder="请选择项目"
            style="width: 100%"
            :disabled="resourceUpload.fileDialogMode === 'edit'"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <!-- 迭代选择器：仅在"全部"视图下或编辑模式下显示 -->
        <el-form-item
          label="所属迭代"
          prop="iteration_id"
          v-if="
            resourceList.filterForm.project_id &&
            (iterationManager.selectedIterationId === null ||
              resourceUpload.fileDialogMode === 'edit')
          "
        >
          <el-select
            v-model="resourceUpload.fileFormData.iteration_id"
            placeholder="请选择所属迭代"
            style="width: 100%"
            clearable
          >
            <el-option
              label="不归属任何迭代（未分类）"
              :value="RESOURCE_CONFIG.ITERATION_UNCLASSIFIED"
            />
            <template v-if="Array.isArray(validIterationsForSelectArray)">
              <el-option
                v-for="(it, idx) in validIterationsForSelectArray"
                :key="'iter-' + (it?.id ?? idx)"
                :label="`${it?.name ?? '未知'} (${it?.version ?? 'v1.0'})`"
                :value="it?.id"
              />
            </template>
          </el-select>
        </el-form-item>

        <!-- 已选迭代提示：在具体迭代或未分类视图下显示 -->
        <el-form-item
          label="所属迭代"
          v-if="resourceList.filterForm.project_id && iterationManager.selectedIterationId !== null"
        >
          <div class="iteration-hint">
            <el-tag v-if="iterationManager.selectedIterationId === 0" type="info">未分类</el-tag>
            <el-tag v-else type="success">{{ iterationManager.getCurrentIterationTitle() }}</el-tag>
          </div>
        </el-form-item>

        <el-form-item label="资源名称" prop="name">
          <el-input
            v-model="resourceUpload.fileFormData.name"
            placeholder="如：需求文档v1.2、洪恩UI原型图v1.0"
          />
        </el-form-item>

        <el-form-item label="资源类型" prop="resource_type">
          <el-select
            v-model="resourceUpload.fileFormData.resource_type"
            placeholder="请选择资源类型"
            style="width: 100%"
          >
            <el-option
              v-for="option in RESOURCE_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="resourceUpload.fileDialogMode === 'add'" label="选择文件" prop="file">
          <el-upload
            ref="resourceUpload.uploadRef"
            class="upload-component"
            action=""
            :auto-upload="false"
            :limit="resourceUpload.isBatchUpload ? RESOURCE_CONFIG.MAX_BATCH_UPLOAD : 1"
            :multiple="resourceUpload.isBatchUpload"
            :on-change="resourceUpload.handleFileChange"
            :on-remove="resourceUpload.handleFileRemove"
            :on-exceed="resourceUpload.handleExceed"
            :accept="resourceUpload.isBatchUpload ? BATCH_FILE_ACCEPT : SINGLE_FILE_ACCEPT"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text" v-if="resourceUpload.isBatchUpload">
              拖拽文件到此处，或<em>点击上传</em>（最多{{
                RESOURCE_CONFIG.MAX_BATCH_UPLOAD
              }}张，支持ZIP压缩包）
            </div>
            <div class="el-upload__text" v-else>拖拽文件到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip" v-if="resourceUpload.isBatchUpload">
                支持批量上传UI原型图：png, jpg, jpeg, gif, webp, bmp 格式，最多{{
                  RESOURCE_CONFIG.MAX_BATCH_UPLOAD
                }}张；也支持上传ZIP压缩包，系统将自动解压提取图片
              </div>
              <div class="el-upload__tip" v-else>
                支持 txt, doc, docx, pdf, md, xlsx, xls, csv, json, yaml, png, jpg, gif, zip, rar
                格式
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="resourceUpload.fileFormData.description"
            type="textarea"
            :rows="2"
            placeholder="资源描述（可选）"
          />
        </el-form-item>

        <el-form-item
          v-if="resourceUpload.fileDialogMode !== 'add' || !resourceUpload.isBatchUpload"
          label="启用状态"
        >
          <el-switch v-model="resourceUpload.fileFormData.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="resourceUpload.fileDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleFileSubmitWrapper"
          :loading="resourceUpload.isSubmitting"
          >确定</el-button
        >
      </template>
    </el-dialog>

    <!-- 迭代弹窗 -->
    <el-dialog
      v-model="iterationManager.iterationDialogVisible"
      :title="iterationManager.iterationDialogMode === 'add' ? '新建迭代' : '编辑迭代'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="iterationFormLocalRef"
        :model="iterationManager.iterationFormData"
        :rules="iterationManager.iterationFormRules"
        label-width="100px"
      >
        <el-form-item label="迭代名称" prop="name">
          <el-input
            v-model="iterationManager.iterationFormData.name"
            placeholder="请输入迭代名称"
          />
        </el-form-item>
        <el-form-item label="版本号" prop="version">
          <el-input v-model="iterationManager.iterationFormData.version" placeholder="如 v1.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="iterationManager.iterationFormData.description"
            type="textarea"
            :rows="2"
            placeholder="迭代描述（可选）"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select
            v-model="iterationManager.iterationFormData.status"
            placeholder="请选择状态"
            style="width: 100%"
          >
            <el-option
              v-for="option in ITERATION_STATUS_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="iterationManager.iterationFormData.start_date"
            type="date"
            placeholder="选择开始日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="iterationManager.iterationFormData.end_date"
            type="date"
            placeholder="选择结束日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="iterationManager.iterationDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleIterationSubmitWrapper"
          :loading="iterationManager.isSubmitting"
          >确定</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload,
  UploadFilled,
  Plus,
  MoreFilled,
  FolderOpened,
  Document,
  Picture,
  Files,
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useIterationManager, type SafeIteration } from '@/composables/useIterationManager'
import { useResourceList } from '@/composables/useResourceList'
import { useResourceUpload } from '@/composables/useResourceUpload'
import { useResourceOperations } from '@/composables/useResourceOperations'
import {
  RESOURCE_CONFIG,
  RESOURCE_TYPE_OPTIONS,
  ITERATION_STATUS_OPTIONS,
  SINGLE_FILE_ACCEPT,
  BATCH_FILE_ACCEPT,
} from '@/constants/resource'

interface Project {
  id: number
  name: string
}

// 资源类型定义
interface Resource {
  id: number
  project_id: number
  name: string
  resource_type: string
  source_type?: 'file' | 'ui_prototype'
  screen_count?: number
  is_active: boolean
  upload_time?: string
  created_at?: string
  iteration_id?: number
  prototype_project_id?: number
}

// 初始化 Composables
const iterationManager = useIterationManager()
const resourceList = useResourceList(iterationManager)
const resourceUpload = useResourceUpload(iterationManager, () => {
  resourceList.getResources()
})
const resourceOperations = useResourceOperations(iterationManager, () => {
  resourceList.getResources()
})

// 迭代表单本地 ref（解决模板 ref 绑定 composable 内部 ref 的问题）
const iterationFormLocalRef = ref()

// 文件表单本地 ref（解决模板 ref 绑定 composable 内部 ref 的问题）
const fileFormLocalRef = ref()

// 辅助计算属性 - 用于解决模板类型推断问题
const safeIterationsArray = computed(() => iterationManager.safeIterations as SafeIteration[])
const validIterationsForSelectArray = computed(
  () => iterationManager.validIterationsForSelect as SafeIteration[]
)

// 辅助函数 - 安全访问迭代统计信息
const getIterationStats = (id: number) => {
  const stats = (iterationManager.iterationStats as any).value?.[id]
  return {
    files: stats?.files ?? 0,
    prototypes: stats?.prototypes ?? 0,
  }
}

// 项目列表（独立状态，不属于任何 composable）
const projects = ref<Project[]>([])

/**
 * 获取项目列表
 */
const getProjects = async () => {
  try {
    const response = await request.get('/api/v1/project/list', {
      params: { page: 1, page_size: 100 },
    })
    if (response && response.data && response.data.items) {
      projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
    } else {
      projects.value = []
    }
  } catch (error) {
    console.error('获取项目列表失败:', error)
    projects.value = []
  }
}

/**
 * 包装方法：选择迭代并刷新数据
 */
const handleSelectIterationAndRefresh = async (iterationId: number | null) => {
  try {
    iterationManager.handleSelectIteration(iterationId)
    resourceList.pagination.page = 1 // 切换迭代时重置分页到第1页
    await resourceList.getResources() // 重新加载数据
  } catch (error) {
    console.error('切换迭代失败:', error)
    ElMessage.error('切换迭代失败，请重试')
  }
}

/**
 * 包装方法：新建迭代
 */
const handleAddIterationWrapper = () => {
  iterationManager.handleAddIteration(Number(resourceList.filterForm.project_id))
}

/**
 *包装方法：新增文件
 */
const handleAddFileWrapper = () => {
  if (!resourceList.filterForm.project_id) {
    ElMessage.warning('请先选择项目')
    return
  }
  resourceUpload.resetFileForm()
  resourceUpload.fileDialogMode = 'add'
  resourceUpload.fileFormData.project_id = resourceList.filterForm.project_id as number

  // 根据当前选中的迭代设置默认值
  if (iterationManager.selectedIterationId !== null && iterationManager.selectedIterationId !== 0) {
    resourceUpload.fileFormData.iteration_id = iterationManager.selectedIterationId
  } else if (iterationManager.selectedIterationId === 0) {
    // "未分类"视图：默认选择"不归属任何迭代"，隐藏选择器
    resourceUpload.fileFormData.iteration_id = 0
  } else {
    // "全部"视图（selectedIterationId为null）：显示选择器，让用户自己选择
    resourceUpload.fileFormData.iteration_id = null
  }

  resourceUpload.fileDialogVisible = true
}

/**
 * 包装方法：提交文件表单
 */
const handleFileSubmitWrapper = async () => {
  if (!fileFormLocalRef.value) {
    ElMessage.error('表单初始化失败，请刷新页面重试')
    return
  }

  await resourceUpload.handleFileSubmit(fileFormLocalRef.value)
}

/**
 * 包装方法：编辑资源（判断是否跳转或打开弹窗）
 */
const handleEditWrapper = (row: Resource) => {
  const shouldOpenDialog = resourceOperations.handleEditNavigation(row)
  if (shouldOpenDialog) {
    // 需要在弹窗中编辑
    resourceUpload.handleEdit(row)
  }
}

/**
 * 包装方法：处理迭代操作命令
 */
const handleIterationCommandWrapper = async (command: string, iteration: SafeIteration) => {
  const needRefresh = await iterationManager.handleIterationCommand(command, iteration as any)
  if (needRefresh) {
    await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
    await resourceList.getResources()
  }
}

/**
 * 包装方法：提交迭代表单
 */
const handleIterationSubmitWrapper = async () => {
  if (!iterationFormLocalRef.value) {
    ElMessage.error('表单初始化失败，请刷新页面重试')
    return
  }

  try {
    await iterationFormLocalRef.value.validate()
  } catch {
    return
  }

  const needRefresh = await iterationManager.handleIterationSubmit(iterationFormLocalRef.value)
  if (needRefresh) {
    iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
    resourceList.getResources()
  }
}

/**
 * 重置筛选条件（增强版）
 */
const handleReset = async () => {
  resourceList.handleReset()
  // 额外清空迭代列表（因为 iterations 属于 iterationManager）
  // 注意：这里通过loadIterations传入空值来清空，而不是直接修改内部状态
  if (!resourceList.filterForm.project_id) {
    await iterationManager.loadIterations(0)
  }
}

// 监听项目变化
watch(
  () => resourceList.filterForm.project_id,
  async () => {
    resourceList.pagination.page = 1
    iterationManager.selectedIterationId = null
    if (resourceList.filterForm.project_id) {
      await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
    } else {
      await iterationManager.loadIterations(0)
    }
    await resourceList.getResources()
  }
)

// 监听资源类型变化（用于清空已选文件）
watch(
  () => resourceUpload.fileFormData.resource_type,
  () => {
    resourceUpload.selectedFile = null
    resourceUpload.selectedFiles = []
    resourceUpload.fileFormData.file = null
    if (resourceUpload.uploadRef) {
      resourceUpload.uploadRef.clearFiles()
    }
  }
)

// 页面初始化
let isInitializing = true // 标记是否正在初始化
let initTimer: ReturnType<typeof setTimeout> | null = null // 初始化定时器引用

onMounted(async () => {
  // ✅ 强制关闭所有弹窗（解决自动打开的问题）
  iterationManager.iterationDialogVisible = false
  resourceUpload.fileDialogVisible = false

  try {
    // 步骤1: 先加载项目列表
    await getProjects()

    // 步骤2: 如果没有默认项目且只有一个项目，自动选中
    if (!resourceList.filterForm.project_id && projects.value.length > 0) {
      resourceList.filterForm.project_id = projects.value[0].id
    }

    // 步骤3: 如果已选中项目，加载迭代列表和资源列表
    if (resourceList.filterForm.project_id) {
      await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
      await resourceList.getResources()
    }
  } catch (error) {
    console.error('页面初始化失败:', error)
    ElMessage.error('页面初始化失败，请刷新重试')
  }

  // ✅ 初始化完成后再次强制关闭弹窗，并延迟确保生效
  await nextTick()
  iterationManager.iterationDialogVisible = false
  resourceUpload.fileDialogVisible = false

  initTimer = setTimeout(() => {
    iterationManager.iterationDialogVisible = false
    resourceUpload.fileDialogVisible = false
    isInitializing = false
  }, 500)
})

// ✅ 组件卸载时清理定时器，防止内存泄漏
onUnmounted(() => {
  if (initTimer) {
    clearTimeout(initTimer)
    initTimer = null
  }
})

// ✅ Watch 监控：在初始化阶段阻止弹窗自动打开
watch(
  () => iterationManager.iterationDialogVisible,
  (newVal) => {
    if (isInitializing && newVal === true) {
      nextTick(() => {
        iterationManager.iterationDialogVisible = false
      })
    }
  }
)

watch(
  () => resourceUpload.fileDialogVisible,
  (newVal) => {
    if (isInitializing && newVal === true) {
      nextTick(() => {
        resourceUpload.fileDialogVisible = false
      })
    }
  }
)
</script>

<style scoped>
.resource-manage-container {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
}

.filter-card {
  margin-bottom: 15px;
  flex-shrink: 0;
}

.main-content {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 16px;
}

.iteration-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.iteration-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid #e4e7ed;
  background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.5px;
}

.iteration-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.iteration-card {
  padding: 12px 14px;
  margin-bottom: 6px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.25s ease;
  background: #fff;
}

.iteration-card:hover {
  background: #f5f7fa;
  border-color: #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.iteration-card.active {
  background: linear-gradient(135deg, #ecf5ff 0%, #f0f9ff 100%);
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}

.iteration-card-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.iteration-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
}

.iteration-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.iteration-card.active .iteration-name {
  color: #409eff;
  font-weight: 600;
}

.version-tag {
  flex-shrink: 0;
  font-size: 11px;
  background: #f0f2f5;
  border-color: #e4e7ed;
}

.iteration-stats {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 3px;
}

.stat-item .el-icon {
  font-size: 12px;
}

.iteration-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.more-icon {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.2s;
}

.more-icon:hover {
  color: #409eff;
  background: #ecf5ff;
}

.iteration-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 30px 20px;
  color: #909399;
}

.empty-text {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
  color: #606266;
}

.empty-hint {
  font-size: 12px;
  margin: 0;
  color: #909399;
  text-align: center;
  line-height: 1.5;
}

.resource-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.list-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.list-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.resource-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}

.resource-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.resource-actions {
  display: flex;
  gap: 8px;
}

.pagination {
  margin-top: 15px;
  display: flex;
  justify-content: flex-end;
}

.resource-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.screen-count-tag {
  flex-shrink: 0;
}

.upload-component {
  width: 100%;
}

.upload-component :deep(.el-upload) {
  width: 100%;
}

.upload-component :deep(.el-upload-dragger) {
  width: 100%;
}

.iteration-hint {
  display: flex;
  align-items: center;
}

.empty-resources {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 8px 0 0;
}

.empty-desc {
  font-size: 14px;
  color: #909399;
  margin: 0 0 16px;
}
</style>
