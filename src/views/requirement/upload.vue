<template>
  <div class="requirement-upload">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>上传需求</span>
          <el-button type="primary" @click="goBack">返回列表</el-button>
        </div>
      </template>
      
      <el-form :model="form" label-width="80px">
        <el-form-item label="项目选择">
          <el-select v-model="form.project_id" placeholder="请选择项目" style="width: 100%" @change="handleProjectChange">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <!-- 迭代选择器：仅在选择了项目后显示 -->
        <el-form-item label="所属迭代" v-if="form.project_id">
          <el-select
            v-model="form.iteration_id"
            placeholder="请选择所属迭代（可选）"
            clearable
            style="width: 100%"
          >
            <el-option label="不归属任何迭代" :value="0" />
            <el-option
              v-for="it in iterations"
              :key="it.id"
              :label="`${it.name} (${it.version})`"
              :value="it.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="需求文件">
          <el-upload
            class="upload-demo"
            action=""
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            :limit="1"
            accept=".txt,.doc,.docx,.pdf,.md"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                请上传需求文件，支持 .txt, .doc, .docx, .pdf, .md 格式
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item label="需求描述">
          <el-input
            type="textarea"
            v-model="form.description"
            placeholder="请输入需求描述"
            :rows="4"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleUpload" :loading="loading">
            上传需求
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from '@/utils/request'
import { iterationApi } from '@/api/iteration'
import type { Iteration } from '@/api/iteration'

interface Project {
  id: number
  name: string
}

const router = useRouter()
const route = useRoute()
const projects = ref<Project[]>([])
const iterations = ref<Iteration[]>([]) // 迭代列表
const fileList = ref<any[]>([])
const loading = ref(false)
const form = ref({
  project_id: '' as number | '',
  iteration_id: undefined as number | undefined, // 所属迭代ID
  description: ''
})

// 获取项目列表
const getProjects = async () => {
  try {
    const response = await axios.get('/api/v1/project/list')
    projects.value = response.data.items
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

// 加载迭代列表
const loadIterations = async (projectId: number) => {
  try {
    const response = await iterationApi.getIterations(projectId)
    iterations.value = response.data?.items || []
  } catch (error) {
    console.error('获取迭代列表失败:', error)
    iterations.value = []
  }
}

// 项目选择变更时重新加载迭代列表
const handleProjectChange = (projectId: number) => {
  form.value.iteration_id = undefined // 重置迭代选择
  if (projectId) {
    loadIterations(projectId)
  } else {
    iterations.value = []
  }
}

// 处理文件选择
const handleFileChange = (file: any) => {
  fileList.value = [file]
}

// 处理文件上传
const handleUpload = async () => {
  if (!form.value.project_id) {
    ElMessage.warning('请选择项目')
    return
  }

  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }

  loading.value = true

  try {
    const file = fileList.value[0].raw
    const formData = new FormData()
    formData.append('file', file)
    formData.append('project_id', form.value.project_id.toString())

    // ✅ 修复：使用统一的iteration_id转换逻辑（0表示未分类，需转为-1传给后端）
    if (form.value.iteration_id !== undefined && form.value.iteration_id !== null) {
      const iterationValue = form.value.iteration_id === 0 ? -1 : form.value.iteration_id
      formData.append('iteration_id', iterationValue.toString())
    }

    await axios.post('/api/v1/file/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success('需求上传成功')
    router.push('/home/requirement')
  } catch (error) {
    ElMessage.error('需求上传失败')
    console.error('上传失败:', error)
  } finally {
    loading.value = false
  }
}

// 返回列表
const goBack = () => {
  router.push('/home/requirement')
}

// 初始化
onMounted(async () => {
  await getProjects()

  // 从URL参数接收iteration_id（如果存在）
  if (route.query.iteration_id) {
    form.value.iteration_id = Number(route.query.iteration_id)
  }

  // 如果URL中也有project_id参数，预填项目并加载迭代列表
  if (route.query.project_id) {
    form.value.project_id = Number(route.query.project_id)
    // 加载该项目的迭代列表
    await loadIterations(Number(route.query.project_id))
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-demo {
  margin-top: 10px;
}
</style>