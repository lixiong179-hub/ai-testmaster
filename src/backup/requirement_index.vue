<template>
  <div class="requirement-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>资源列表</span>
          <el-button type="primary" @click="handleUpload">上传需求</el-button>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project_id" placeholder="请选择项目" style="width: 200px">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getFiles">查询</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="files" style="width: 100%">
        <el-table-column prop="id" label="文件ID" width="80" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="file_type" label="文件类型" width="100" />
        <el-table-column prop="size" label="文件大小" width="100">
          <template #default="scope">
            {{ formatFileSize(scope.row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" width="180" />
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleAnalyze(scope.row)">
              AI分析
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FileAPI, type ProjectFile } from '@/api/file'
import request from '@/utils/request'

interface Project {
  id: number
  name: string
}

const router = useRouter()
const route = useRoute()
const projects = ref<Project[]>([])
const files = ref<ProjectFile[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchForm = ref({
  project_id: '' as number | ''
})

// 获取项目列表
const getProjects = async () => {
  try {
    const response = await request.get('/api/v1/project/list')
    console.log('获取项目列表响应:', response)
    // 过滤掉名称为 "默认项目" 的项目
    if (response && response.data && response.data.items) {
      projects.value = response.data.items.filter((project: Project) => project.name !== '默认项目')
      console.log('过滤后的项目列表:', projects.value)
    } else {
      projects.value = []
      console.log('没有获取到项目列表')
    }
    
    // 如果URL中有project_id参数，设置为默认值
    const projectId = route.query.project_id
    if (projectId) {
      searchForm.value.project_id = Number(projectId)
    }
  } catch (error) {
    console.error('获取项目列表失败:', error)
    projects.value = []
  }
}

// 获取文件列表
const getFiles = async () => {
  try {
    console.log('开始获取文件列表，project_id:', searchForm.value.project_id)
    if (!searchForm.value.project_id) {
      // 获取所有项目的文件列表
      console.log('调用 FileAPI.getAllFiles()')
      const response = await FileAPI.getAllFiles()
      console.log('获取所有文件列表响应:', response)
      if (response && response.data) {
        files.value = response.data.items || []
        total.value = response.data.total || 0
        console.log('获取到的文件列表:', files.value)
        console.log('文件总数:', total.value)
      } else {
        files.value = []
        total.value = 0
        console.log('没有获取到文件列表')
      }
    } else {
      // 获取指定项目的文件列表
      console.log('调用 FileAPI.getFileList(', searchForm.value.project_id, ')')
      const response = await FileAPI.getFileList(Number(searchForm.value.project_id))
      console.log('获取指定项目文件列表响应:', response)
      if (response && response.data) {
        files.value = response.data.items || []
        total.value = response.data.total || 0
        console.log('获取到的文件列表:', files.value)
        console.log('文件总数:', total.value)
      } else {
        files.value = []
        total.value = 0
        console.log('没有获取到文件列表')
      }
    }
  } catch (error) {
    console.error('获取文件列表失败:', error)
    files.value = []
    total.value = 0
    ElMessage.error('获取文件列表失败')
  }
}

// 处理分页
const handleSizeChange = (size: number) => {
  pageSize.value = size
  getFiles()
}

const handleCurrentChange = (current: number) => {
  page.value = current
  getFiles()
}

// 处理上传需求
const handleUpload = () => {
  router.push('/home/requirement/upload')
}

// 处理AI分析
const handleAnalyze = (file: ProjectFile) => {
  // 跳转到测试点管理页，并传递文件信息以打开提取对话框
  router.push({
    path: '/home/case/test-point-management',
    query: {
      projectId: String(file.project_id),
      file_id: String(file.id),
      filename: file.file_name,
      openExtract: '1',
    }
  })
}

// 处理删除文件
const handleDelete = (file: ProjectFile) => {
  ElMessageBox.confirm(
    '确定要删除这个文件吗？',
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await FileAPI.deleteFile(file.id, file.project_id)
      ElMessage.success('删除成功')
      getFiles()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  })
}

// 格式化文件大小
const formatFileSize = (size?: number): string => {
  if (!size) return '-'
  if (size < 1024) {
    return size + ' B'
  } else if (size < 1024 * 1024) {
    return (size / 1024).toFixed(2) + ' KB'
  } else {
    return (size / (1024 * 1024)).toFixed(2) + ' MB'
  }
}

// 初始化
onMounted(() => {
  getProjects()
  getFiles()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>