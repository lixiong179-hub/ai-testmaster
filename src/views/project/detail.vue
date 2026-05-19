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
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目ID">{{ projectStore.currentProject.id }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ projectStore.currentProject.name }}</el-descriptions-item>
          <el-descriptions-item label="项目类型">
            <el-tag :type="projectStore.currentProject.project_type === 'web' ? 'success' : 'warning'">
              {{ projectStore.currentProject.project_type === 'web' ? 'Web端' : 'C端' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusText(projectStore.currentProject.status) }}</el-descriptions-item>
          <el-descriptions-item label="项目描述" :span="2">{{ projectStore.currentProject.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ projectStore.currentProject.create_time }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ projectStore.currentProject.update_time }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="projectStore.currentProject.project_type === 'web'" class="env-config-section">
          <el-divider content-position="left">Web端多环境配置</el-divider>
          <el-form :model="webEnvForm" label-width="100px">
            <el-form-item label="测试环境">
              <el-row :gutter="12">
                <el-col :span="12"><el-input v-model="webEnvForm.test.url" placeholder="测试环境URL" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.test.username" placeholder="账号" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.test.password" type="password" placeholder="密码" show-password clearable /></el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="灰度环境">
              <el-row :gutter="12">
                <el-col :span="12"><el-input v-model="webEnvForm.staging.url" placeholder="灰度环境URL" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.staging.username" placeholder="账号" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.staging.password" type="password" placeholder="密码" show-password clearable /></el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="正式环境">
              <el-row :gutter="12">
                <el-col :span="12"><el-input v-model="webEnvForm.prod.url" placeholder="正式环境URL" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.prod.username" placeholder="账号" clearable /></el-col>
                <el-col :span="5"><el-input v-model="webEnvForm.prod.password" type="password" placeholder="密码" show-password clearable /></el-col>
              </el-row>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveWebEnvConfig" :loading="saving">保存配置</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div v-else class="device-config-section">
          <el-divider content-position="left">C端设备配置</el-divider>
          <el-alert type="info" :closable="false" show-icon>C端测试功能正在开发中，设备配置功能暂不可用。</el-alert>
          <el-form :model="deviceForm" label-width="120px" style="margin-top: 20px; max-width: 600px">
            <el-form-item label="设备平台">
              <el-select v-model="deviceForm.platform" placeholder="请选择平台">
                <el-option label="Android" value="android" />
                <el-option label="iOS" value="ios" />
              </el-select>
            </el-form-item>
            <el-form-item label="设备ID"><el-input v-model="deviceForm.device_id" placeholder="设备ID" clearable /></el-form-item>
            <el-form-item label="设备名称"><el-input v-model="deviceForm.device_name" placeholder="设备名称" clearable /></el-form-item>
            <el-form-item label="App包名"><el-input v-model="deviceForm.app_package" placeholder="App包名，如：com.example.app" clearable /></el-form-item>
            <el-form-item label="Appium地址"><el-input v-model="deviceForm.appium_url" placeholder="http://localhost:4723" clearable /></el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveDeviceConfig" :loading="saving">保存配置</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="file-upload-section">
          <el-divider content-position="left">文件上传</el-divider>
          <RequirementUploader :project-id="projectId" accept=".doc,.docx,.pdf,.xlsx,.png,.jpg" @success="handleUploadSuccess" />
        </div>

        <div class="file-list-section">
          <el-divider content-position="left">文件列表</el-divider>
          <el-table v-loading="projectStore.loading" :data="projectStore.projectFiles" style="width: 100%" border>
            <el-table-column prop="id" label="文件ID" width="80" />
            <el-table-column prop="file_name" label="文件名称">
              <template #default="scope"><el-link :href="scope.row.file_url" target="_blank">{{ scope.row.file_name }}</el-link></template>
            </el-table-column>
            <el-table-column prop="file_type" label="文件类型" width="100" />
            <el-table-column prop="file_source" label="来源" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.file_source === 'file' ? 'success' : 'info'">{{ scope.row.file_source === 'file' ? '本地上传' : 'URL链接' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="size" label="文件大小" width="100">
              <template #default="scope">{{ scope.row.size ? `${scope.row.size} KB` : '-' }}</template>
            </el-table-column>
            <el-table-column prop="upload_time" label="上传时间" width="180" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="scope"><el-button size="small" type="danger" @click="confirmDeleteFile(scope.row.id)">删除</el-button></template>
            </el-table-column>
          </el-table>
          <div v-if="projectStore.projectFiles.length === 0" class="empty-state"><el-empty description="暂无文件" /></div>
        </div>
      </div>

      <div v-else class="loading"><el-skeleton :rows="10" animated /></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import RequirementUploader from '@/components/RequirementUploader.vue'
import { useProjectDetail } from './useProjectDetail'

const {
  projectStore, saving, webEnvForm, deviceForm, projectId,
  getStatusText, saveWebEnvConfig, saveDeviceConfig, handleUploadSuccess, confirmDeleteFile, goBack,
} = useProjectDetail()
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
