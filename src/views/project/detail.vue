<template>
  <div class="project-detail">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目详情</span>
          <el-button type="primary" size="small" @click="goBack">返回列表</el-button>
        </div>
      </template>

      <div v-if="projectStore.currentProject" class="project-info">
        <!-- 项目基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目ID">{{
            projectStore.currentProject.id
          }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{
            projectStore.currentProject.name
          }}</el-descriptions-item>
          <el-descriptions-item label="项目类型">
            <el-tag
              :type="projectStore.currentProject.project_type === 'web' ? 'success' : 'warning'"
            >
              {{ projectStore.currentProject.project_type === 'web' ? 'Web端' : 'C端' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{
            getStatusText(projectStore.currentProject.status)
          }}</el-descriptions-item>
          <el-descriptions-item label="项目描述" :span="2">{{
            projectStore.currentProject.description || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{
            projectStore.currentProject.create_time
          }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{
            projectStore.currentProject.update_time
          }}</el-descriptions-item>
        </el-descriptions>

        <!-- Web端多环境配置 -->
        <div v-if="projectStore.currentProject.project_type === 'web'" class="env-config-section">
          <el-divider content-position="left">Web端多环境配置</el-divider>
          <el-form :model="webEnvForm" label-width="100px">
            <!-- 测试环境 -->
            <el-form-item label="测试环境">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-input v-model="webEnvForm.test.url" placeholder="测试环境URL" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input v-model="webEnvForm.test.username" placeholder="账号" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input
                    v-model="webEnvForm.test.password"
                    type="password"
                    placeholder="密码"
                    show-password
                    clearable
                  />
                </el-col>
              </el-row>
            </el-form-item>
            <!-- 灰度环境 -->
            <el-form-item label="灰度环境">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-input v-model="webEnvForm.staging.url" placeholder="灰度环境URL" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input v-model="webEnvForm.staging.username" placeholder="账号" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input
                    v-model="webEnvForm.staging.password"
                    type="password"
                    placeholder="密码"
                    show-password
                    clearable
                  />
                </el-col>
              </el-row>
            </el-form-item>
            <!-- 正式环境 -->
            <el-form-item label="正式环境">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-input v-model="webEnvForm.prod.url" placeholder="正式环境URL" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input v-model="webEnvForm.prod.username" placeholder="账号" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input
                    v-model="webEnvForm.prod.password"
                    type="password"
                    placeholder="密码"
                    show-password
                    clearable
                  />
                </el-col>
              </el-row>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveWebEnvConfig" :loading="saving"
                >保存配置</el-button
              >
            </el-form-item>
          </el-form>
        </div>

        <!-- C端设备配置 -->
        <div v-else class="device-config-section">
          <el-divider content-position="left">C端设备配置</el-divider>
          <el-alert type="info" :closable="false" show-icon>
            C端测试功能正在开发中，设备配置功能暂不可用。
          </el-alert>
          <el-form
            :model="deviceForm"
            label-width="120px"
            style="margin-top: 20px; max-width: 600px"
          >
            <el-form-item label="设备平台">
              <el-select v-model="deviceForm.platform" placeholder="请选择平台">
                <el-option label="Android" value="android" />
                <el-option label="iOS" value="ios" />
              </el-select>
            </el-form-item>
            <el-form-item label="设备ID">
              <el-input v-model="deviceForm.device_id" placeholder="设备ID" clearable />
            </el-form-item>
            <el-form-item label="设备名称">
              <el-input v-model="deviceForm.device_name" placeholder="设备名称" clearable />
            </el-form-item>
            <el-form-item label="App包名">
              <el-input
                v-model="deviceForm.app_package"
                placeholder="App包名，如：com.example.app"
                clearable
              />
            </el-form-item>
            <el-form-item label="Appium地址">
              <el-input
                v-model="deviceForm.appium_url"
                placeholder="http://localhost:4723"
                clearable
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveDeviceConfig" :loading="saving"
                >保存配置</el-button
              >
            </el-form-item>
          </el-form>
        </div>

        <!-- 文件上传 -->
        <div class="file-upload-section">
          <el-divider content-position="left">文件上传</el-divider>
          <el-upload
            class="upload-demo"
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            accept=".doc,.docx,.pdf,.xlsx,.png,.jpg"
            multiple
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持上传：docx、pdf、xlsx、png、jpg格式文件</div>
            </template>
          </el-upload>
          <el-button
            type="primary"
            @click="uploadFiles"
            :disabled="fileList.length === 0"
            style="margin-top: 10px"
            >开始上传</el-button
          >
        </div>

        <!-- 文件列表 -->
        <div class="file-list-section">
          <el-divider content-position="left">文件列表</el-divider>
          <el-table
            v-loading="projectStore.loading"
            :data="projectStore.projectFiles"
            style="width: 100%"
            border
          >
            <el-table-column prop="id" label="文件ID" width="80" />
            <el-table-column prop="file_name" label="文件名称">
              <template #default="scope">
                <el-link :href="scope.row.file_url" target="_blank">{{
                  scope.row.file_name
                }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="file_type" label="文件类型" width="100" />
            <el-table-column prop="file_source" label="来源" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.file_source === 'file' ? 'success' : 'info'">
                  {{ scope.row.file_source === 'file' ? '本地上传' : 'URL链接' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="文件大小" width="100">
              <template #default="scope">
                {{ scope.row.size ? `${scope.row.size} KB` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="upload_time" label="上传时间" width="180" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="scope">
                <el-button size="small" type="danger" @click="confirmDeleteFile(scope.row.id)"
                  >删除</el-button
                >
              </template>
            </el-table-column>
          </el-table>
          <div v-if="projectStore.projectFiles.length === 0" class="empty-state">
            <el-empty description="暂无文件" />
          </div>
        </div>
      </div>

      <div v-else class="loading">
        <el-skeleton :rows="10" animated />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/project'
import { UploadFilled } from '@element-plus/icons-vue'
import { ProjectAPI, type WebEnvConfigs, type DeviceConfig, type Project } from '@/api/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const fileList = ref<any[]>([])
const saving = ref(false)

const webEnvForm = reactive({
  test: { url: '', username: '', password: '' },
  staging: { url: '', username: '', password: '' },
  prod: { url: '', username: '', password: '' },
})

const deviceForm = reactive({
  platform: '' as 'android' | 'ios' | '',
  device_id: '',
  device_name: '',
  app_package: '',
  appium_url: '',
})

const projectId = ref<number>(0)

// 获取状态文本
const getStatusText = (status: number) => {
  const statusMap: Record<number, string> = { 0: '未激活', 1: '正常', 2: '归档' }
  return statusMap[status] || '未知'
}

const PASSWORD_MASK = '******'

// 加载配置（从 fetchProjectDetail 返回的数据中提取，避免重复请求）
const loadConfig = () => {
  const project = projectStore.currentProject as
    | (Project & { web_env_configs?: WebEnvConfigs; device_config?: DeviceConfig })
    | null
  if (!project) return
  if (project.project_type === 'web' && project.web_env_configs) {
    const cfg = project.web_env_configs
    if (cfg.test)
      webEnvForm.test = {
        ...webEnvForm.test,
        ...cfg.test,
        password: cfg.test.password === PASSWORD_MASK ? '' : cfg.test.password || '',
      }
    if (cfg.staging)
      webEnvForm.staging = {
        ...webEnvForm.staging,
        ...cfg.staging,
        password: cfg.staging.password === PASSWORD_MASK ? '' : cfg.staging.password || '',
      }
    if (cfg.prod)
      webEnvForm.prod = {
        ...webEnvForm.prod,
        ...cfg.prod,
        password: cfg.prod.password === PASSWORD_MASK ? '' : cfg.prod.password || '',
      }
  } else if (project.device_config?.default_device) {
    const d = project.device_config.default_device
    deviceForm.platform = (d.platform as 'android' | 'ios') || ''
    deviceForm.device_id = d.device_id || ''
    deviceForm.device_name = d.device_name || ''
    deviceForm.app_package = d.app_package || ''
    deviceForm.appium_url = d.appium_url || ''
  }
}

// 保存Web环境配置
const saveWebEnvConfig = async () => {
  saving.value = true
  try {
    const buildPayload = (envData: { url: string; username: string; password: string }) => {
      const payload: Record<string, string> = {}
      if (envData.url !== undefined) payload.url = envData.url
      if (envData.username !== undefined) payload.username = envData.username
      if (envData.password && envData.password !== PASSWORD_MASK) {
        payload.password = envData.password
      }
      return payload
    }

    const res = await ProjectAPI.updateProjectConfig(projectId.value, {
      project_type: 'web',
      web_env_configs: {
        test: buildPayload(webEnvForm.test),
        staging: buildPayload(webEnvForm.staging),
        prod: buildPayload(webEnvForm.prod),
      } as WebEnvConfigs,
    })
    if (res.code === 200) {
      ElMessage.success('Web环境配置保存成功')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// 保存C端设备配置
const saveDeviceConfig = async () => {
  saving.value = true
  try {
    const res = await ProjectAPI.updateProjectConfig(projectId.value, {
      project_type: 'app',
      device_config: {
        default_device: {
          platform: deviceForm.platform || undefined,
          device_id: deviceForm.device_id || undefined,
          device_name: deviceForm.device_name || undefined,
          app_package: deviceForm.app_package || undefined,
          appium_url: deviceForm.appium_url || undefined,
        },
      },
    })
    if (res.code === 200) {
      ElMessage.success('设备配置保存成功')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// 处理文件变化
const handleFileChange = (_file: any, list: any[]) => {
  fileList.value = list
}

// 上传文件
const uploadFiles = async () => {
  for (const file of fileList.value) {
    await projectStore.uploadFile(projectId.value, file.raw)
  }
  fileList.value = []
}

// 确认删除文件
const confirmDeleteFile = (fileId: number) => {
  ElMessageBox.confirm('确定要删除此文件吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await projectStore.deleteFile(fileId, projectId.value)
    })
    .catch(() => {})
}

// 返回项目列表
const goBack = () => {
  router.push('/home/project')
}

// 页面加载时获取项目详情
onMounted(async () => {
  const id = route.query.id
  if (id) {
    projectId.value = Number(id)
    await projectStore.fetchProjectDetail(projectId.value)
    loadConfig()
  } else {
    ElMessage.error('项目ID不能为空')
    goBack()
  }
})

onUnmounted(() => {
  projectStore.resetState()
})
</script>

<style scoped>
.project-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-info {
  margin-top: 20px;
}

.env-config-section,
.device-config-section,
.file-upload-section,
.file-list-section {
  margin-top: 30px;
}

.empty-state {
  margin-top: 50px;
  text-align: center;
}

.loading {
  margin-top: 20px;
}
</style>
