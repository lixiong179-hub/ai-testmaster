<template>
  <div class="project-list">
    <el-card class="project-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">项目列表</div>
            <div class="card-subtitle">从项目进入任务、执行与测试点管理，是整条测试业务链路的起点。</div>
          </div>
          <el-button type="primary" @click="openCreateDialog">创建项目</el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索项目名称"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">搜索</el-button>
          </template>
        </el-input>
        <el-tag effect="plain" type="info">共 {{ projectStore.total }} 个项目</el-tag>
      </div>

      <el-table
        class="project-table"
        v-loading="projectStore.loading"
        :data="filteredProjects"
        style="width: 100%"
        border
      >
        <el-table-column prop="id" label="项目ID" width="80" />
        <el-table-column prop="name" label="项目名称">
          <template #default="scope">
            <el-link @click="goToDetail(scope.row.id)">{{ scope.row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="project_type" label="项目类型" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.project_type === 'web' ? 'success' : 'warning'">
              {{ scope.row.project_type === 'web' ? 'Web端' : 'C端' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="项目描述" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <el-space wrap>
              <el-button size="small" @click="goToDetail(scope.row.id)">详情</el-button>
              <el-button size="small" type="primary" plain @click="goToTaskList(scope.row.id)">任务</el-button>
              <el-button size="small" type="success" plain @click="goToTestPointManagement(scope.row.id)"
                >测试点</el-button
              >
              <el-button size="small" type="danger" @click="confirmDelete(scope.row.id)"
              >删除</el-button
              >
            </el-space>
          </template>
        </el-table-column>
        <template #empty>
          <div class="project-empty-state">
            <div class="project-empty-title">还没有可用项目</div>
            <div class="project-empty-text">建议先创建项目，后续任务、执行与测试点管理都会围绕项目展开。</div>
            <el-button type="primary" @click="openCreateDialog">创建首个项目</el-button>
          </div>
        </template>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="projectStore.currentPage"
          v-model:page-size="projectStore.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="projectStore.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="dialogVisible" title="创建项目" width="700px">
      <el-form :model="projectForm" :rules="projectRules" ref="projectFormRef" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>

        <el-form-item label="项目类型" prop="project_type">
          <el-radio-group v-model="projectForm.project_type">
            <el-radio value="web">Web端</el-radio>
            <el-radio value="app">C端 (预留)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="项目描述" prop="description">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            placeholder="请输入项目描述"
            :rows="3"
          />
        </el-form-item>

        <!-- Web端环境配置 -->
        <template v-if="projectForm.project_type === 'web'">
          <el-divider content-position="left">Web端多环境配置（选填）</el-divider>

          <!-- 测试环境 -->
          <el-form-item label="测试环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input
                  v-model="projectForm.web_env_configs.test.url"
                  placeholder="测试环境URL"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.test.username"
                  placeholder="账号"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.test.password"
                  type="password"
                  placeholder="密码"
                  show-password
                  autocomplete="new-password"
                />
              </el-col>
            </el-row>
          </el-form-item>

          <!-- 灰度环境 -->
          <el-form-item label="灰度环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input
                  v-model="projectForm.web_env_configs.staging.url"
                  placeholder="灰度环境URL"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.staging.username"
                  placeholder="账号"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.staging.password"
                  type="password"
                  placeholder="密码"
                  show-password
                  autocomplete="new-password"
                />
              </el-col>
            </el-row>
          </el-form-item>

          <!-- 正式环境 -->
          <el-form-item label="正式环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input
                  v-model="projectForm.web_env_configs.prod.url"
                  placeholder="正式环境URL"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.prod.username"
                  placeholder="账号"
                  autocomplete="off"
                />
              </el-col>
              <el-col :span="6">
                <el-input
                  v-model="projectForm.web_env_configs.prod.password"
                  type="password"
                  placeholder="密码"
                  show-password
                  autocomplete="new-password"
                />
              </el-col>
            </el-row>
          </el-form-item>
        </template>

        <!-- C端设备配置 -->
        <template v-else>
          <el-divider content-position="left">C端设备配置（预留）</el-divider>
          <el-form-item>
            <el-alert type="info" :closable="false">
              C端测试功能正在开发中，设备配置功能暂不可用。
            </el-alert>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createProject">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/project'

const router = useRouter()
const projectStore = useProjectStore()

const dialogVisible = ref(false)
const projectFormRef = ref<any>(null)
const searchKeyword = ref('')

const projectForm = ref({
  name: '',
  description: '',
  project_type: 'web' as 'web' | 'app',
  web_env_configs: {
    test: { url: '', username: '', password: '' },
    staging: { url: '', username: '', password: '' },
    prod: { url: '', username: '', password: '' },
  },
})

const projectRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  project_type: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
}

// 过滤项目列表
const filteredProjects = computed(() => {
  if (!searchKeyword.value) {
    return projectStore.projects
  }
  return projectStore.projects.filter((project) =>
    project.name.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

// 获取状态类型
const getStatusType = (status: number) => {
  const statusMap: Record<number, string> = {
    0: 'info',
    1: 'success',
    2: 'warning',
  }
  return statusMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: number) => {
  const statusMap: Record<number, string> = {
    0: '未激活',
    1: '正常',
    2: '归档',
  }
  return statusMap[status] || '未知'
}

// 处理搜索
const handleSearch = () => {
  projectStore.fetchProjects()
}

// 处理页码变化
const handleCurrentChange = (current: number) => {
  projectStore.currentPage = current
  projectStore.fetchProjects()
}

// 处理每页数量变化
const handleSizeChange = (size: number) => {
  projectStore.pageSize = size
  projectStore.currentPage = 1
  projectStore.fetchProjects()
}

// 打开创建项目对话框
const openCreateDialog = () => {
  projectForm.value = {
    name: '',
    description: '',
    project_type: 'web' as 'web' | 'app',
    web_env_configs: {
      test: { url: '', username: '', password: '' },
      staging: { url: '', username: '', password: '' },
      prod: { url: '', username: '', password: '' },
    },
  }
  dialogVisible.value = true
}

// 创建项目
const createProject = async () => {
  if (!projectFormRef.value) return
  await projectFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      const projectId = await projectStore.createProject({
        name: projectForm.value.name,
        description: projectForm.value.description,
        project_type: projectForm.value.project_type,
        web_env_configs:
          projectForm.value.project_type === 'web' ? projectForm.value.web_env_configs : undefined,
      })
      if (projectId) {
        dialogVisible.value = false
        goToDetail(projectId)
      }
    }
  })
}

// 跳转到项目详情页
const goToDetail = (projectId: number) => {
  router.push(`/home/project/detail?id=${projectId}`)
}

const goToTaskList = (projectId: number) => {
  router.push(`/home/task/list/${projectId}`)
}

const goToTestPointManagement = (projectId: number) => {
  router.push({
    path: '/home/case/test-point-management',
    query: {
      projectId: String(projectId),
    },
  })
}

// 确认删除项目
const confirmDelete = (projectId: number) => {
  ElMessageBox.confirm('确定要删除此项目吗？删除后将级联删除关联的文件、测试点和用例。', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await projectStore.deleteProject(projectId)
    })
    .catch(() => {
      // 取消删除
    })
}

// 页面加载时获取项目列表
onMounted(() => {
  projectStore.fetchProjects()
})
</script>

<style scoped>
.project-list {
  padding: 20px;
}


.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.card-subtitle {
  margin-top: 6px;
  color: #7a8594;
  line-height: 1.6;
}

.search-bar {
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 300px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.project-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 16px;
  text-align: center;
}

.project-empty-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.project-empty-text {
  max-width: 420px;
  color: #7a8594;
  line-height: 1.6;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    width: 100%;
  }
}
</style>
