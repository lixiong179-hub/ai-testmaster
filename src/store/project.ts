import { defineStore } from 'pinia'
import {
  ProjectAPI,
  Project,
  ProjectCreateRequest,
  ProjectListResponse,
  ProjectDetailResponse,
} from '@/api/project'
import { FileAPI, ProjectFile, UrlSubmitRequest } from '@/api/file'
import { ElMessage } from 'element-plus'

function getErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as { response?: { data?: { message?: string } } }
  return axiosError?.response?.data?.message || fallback
}

export const useProjectStore = defineStore('project', {
  state: () => ({
    projects: [] as Project[],
    currentProject: null as Project | null,
    projectFiles: [] as ProjectFile[],
    loading: false,
    currentPage: 1,
    pageSize: 10,
    total: 0,
  }),

  getters: {
    getProjectById: (state) => (id: number) => {
      return state.projects.find((project) => project.id === id)
    },
  },

  actions: {
    async fetchProjects() {
      this.loading = true
      try {
        const response: ProjectListResponse = await ProjectAPI.getProjectList({
          page: this.currentPage,
          page_size: this.pageSize,
        })
        this.projects = response?.data?.items || []
        this.total = response?.data?.total || 0
      } catch (error: unknown) {
        console.error('获取项目列表失败，错误:', error)
        ElMessage.error(getErrorMessage(error, '获取项目列表失败'))
      } finally {
        this.loading = false
      }
    },

    async createProject(projectData: ProjectCreateRequest) {
      this.loading = true
      try {
        const response = await ProjectAPI.createProject(projectData)
        ElMessage.success('项目创建成功')
        await this.fetchProjects()
        return response.data.project_id
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '创建项目失败'))
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchProjectDetail(projectId: number) {
      this.loading = true
      try {
        const response: ProjectDetailResponse = await ProjectAPI.getProjectDetail(projectId)
        this.currentProject = response?.data || null
        const rawFiles = response?.data?.files || []
        this.projectFiles = rawFiles.map((f) => ({
          id: f.id,
          project_id: projectId,
          file_name: f.file_name,
          file_type: f.file_type,
          file_url: f.file_url,
          file_source: f.file_source,
          size: f.size,
          upload_time: f.upload_time,
        }))
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '获取项目详情失败'))
      } finally {
        this.loading = false
      }
    },

    async deleteProject(projectId: number) {
      this.loading = true
      try {
        await ProjectAPI.deleteProject(projectId)
        ElMessage.success('项目删除成功')
        await this.fetchProjects()
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '删除项目失败'))
      } finally {
        this.loading = false
      }
    },

    async uploadFile(projectId: number, file: File) {
      this.loading = true
      try {
        await FileAPI.uploadFile(projectId, file)
        ElMessage.success('文件上传成功')
        await this.fetchProjectDetail(projectId)
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '文件上传失败'))
      } finally {
        this.loading = false
      }
    },

    async submitUrl(data: UrlSubmitRequest) {
      this.loading = true
      try {
        await FileAPI.submitUrl(data)
        ElMessage.success('URL提交成功')
        await this.fetchProjectDetail(data.project_id)
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, 'URL提交失败'))
      } finally {
        this.loading = false
      }
    },

    async deleteFile(fileId: number, projectId: number) {
      this.loading = true
      try {
        await FileAPI.deleteFile(fileId, projectId)
        ElMessage.success('文件删除成功')
        await this.fetchProjectDetail(projectId)
      } catch (error: unknown) {
        ElMessage.error(getErrorMessage(error, '文件删除失败'))
      } finally {
        this.loading = false
      }
    },

    resetState() {
      this.projects = []
      this.currentProject = null
      this.projectFiles = []
      this.loading = false
      this.currentPage = 1
      this.pageSize = 10
      this.total = 0
    },
  },
})
