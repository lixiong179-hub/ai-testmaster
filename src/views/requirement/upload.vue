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
          <el-select
            v-model="form.project_id"
            placeholder="请选择项目"
            style="width: 100%"
            @change="handleProjectChange"
          >
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
          <RequirementUploader
            ref="uploaderRef"
            :project-id="form.project_id"
            :iteration-id="normalizedIterationId"
            :description="form.description"
            accept=".txt,.doc,.docx,.pdf,.md"
            :limit="1"
            :show-upload-button="false"
            @success="handleUploadSuccess"
          />
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
          <el-button type="primary" @click="handleSubmit" :loading="loading"> 上传需求 </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { iterationApi } from '@/api/iteration'
import type { Iteration } from '@/api/iteration'
import RequirementUploader from '@/components/RequirementUploader.vue'

interface Project {
  id: number
  name: string
}

const router = useRouter()
const route = useRoute()
const projects = ref<Project[]>([])
const iterations = ref<Iteration[]>([]) // 迭代列表
const loading = ref(false)
const form = ref({
  project_id: '' as number | '',
  iteration_id: undefined as number | undefined, // 所属迭代ID
  description: '',
})
const uploaderRef = ref<InstanceType<typeof RequirementUploader> | null>(null)

const normalizedIterationId = computed<number | null>(() =>
  form.value.iteration_id && form.value.iteration_id > 0 ? form.value.iteration_id : null
)

// 获取项目列表
const getProjects = async () => {
  try {
    const response = await request.get('/api/v1/project/list')
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

const handleSubmit = async () => {
  if (!form.value.project_id) {
    ElMessage.warning('请选择项目')
    return
  }

  loading.value = true
  try {
    const response = await uploaderRef.value?.upload()
    if (!response) {
      return
    }
  } catch (error) {
    ElMessage.error('需求上传失败')
    console.error('上传失败:', error)
  } finally {
    loading.value = false
  }
}

const handleUploadSuccess = () => {
  router.push('/home/requirement')
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
</style>
