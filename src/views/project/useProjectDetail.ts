import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/project'
import { ProjectAPI, type WebEnvConfigs, type DeviceConfig, type Project } from '@/api/project'

const PASSWORD_MASK = '******'

export function useProjectDetail() {
  const route = useRoute()
  const router = useRouter()
  const projectStore = useProjectStore()
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

  const getStatusText = (status: number) => {
    const statusMap: Record<number, string> = { 0: '未激活', 1: '正常', 2: '归档' }
    return statusMap[status] || '未知'
  }

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

  const saveWebEnvConfig = async () => {
    saving.value = true
    try {
      const buildPayload = (envData: { url: string; username: string; password: string }) => {
        const payload: Record<string, string> = {}
        if (envData.url !== undefined) payload.url = envData.url
        if (envData.username !== undefined) payload.username = envData.username
        if (envData.password && envData.password !== PASSWORD_MASK)
          payload.password = envData.password
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
      if (res.code === 200) ElMessage.success('Web环境配置保存成功')
      else ElMessage.error(res.message || '保存失败')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  }

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
      if (res.code === 200) ElMessage.success('设备配置保存成功')
      else ElMessage.error(res.message || '保存失败')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  }

  const handleUploadSuccess = async () => {
    await projectStore.fetchProjectDetail(projectId.value)
  }

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

  const goBack = () => {
    router.push('/home/project')
  }

  const goToResources = () => {
    router.push({ path: '/home/requirement', query: { project_id: String(projectId.value) } })
  }
  const goToTestPoints = () => {
    router.push({
      path: '/home/case/test-point-management',
      query: { projectId: String(projectId.value) },
    })
  }
  const goToCaseList = () => {
    router.push({ path: '/home/case', query: { projectId: String(projectId.value) } })
  }
  const goToTaskList = () => {
    router.push(`/home/task/list/${projectId.value}`)
  }
  const goToReports = () => {
    router.push({ path: '/home/report', query: { project_id: String(projectId.value) } })
  }

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

  return {
    projectStore,
    saving,
    webEnvForm,
    deviceForm,
    projectId,
    getStatusText,
    saveWebEnvConfig,
    saveDeviceConfig,
    handleUploadSuccess,
    confirmDeleteFile,
    goBack,
    goToResources,
    goToTestPoints,
    goToCaseList,
    goToTaskList,
    goToReports,
  }
}
