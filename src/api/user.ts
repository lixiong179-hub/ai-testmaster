import request from '@/utils/request'

export const userApi = {
  getUsers: (params: { skip: number; limit: number }) => request.get('/api/v1/user/', { params }),

  getUser: (userId: number) => request.get(`/api/v1/user/${userId}`),

  createUser: (data: Record<string, unknown>) => request.post('/api/v1/user/', data),

  updateUser: (userId: number, data: Record<string, unknown>) =>
    request.put(`/api/v1/user/${userId}`, data),

  getRoles: (params?: { skip?: number; limit?: number; search?: string }) =>
    request.get('/api/v1/user/role/', { params }),

  createRole: (data: Record<string, unknown>) => request.post('/api/v1/user/role/', data),

  updateRole: (roleId: number, data: Record<string, unknown>) =>
    request.put(`/api/v1/user/role/${roleId}`, data),

  deleteRole: (roleId: number) => request.delete(`/api/v1/user/role/${roleId}`),

  assignRole: (data: { user_id: number; role_id: number }) =>
    request.post('/api/v1/user/role/assign/', data),

  getPermissions: () => request.get('/api/v1/user/permission/'),

  getCurrentUser: () => request.get('/api/v1/user/me'),

  getLoginLogs: (params: { skip: number; limit: number; start_date?: string; end_date?: string }) =>
    request.get('/api/v1/user/login-logs/', { params }),

  changePassword: (data: { old_password: string; new_password: string }) =>
    request.post('/api/v1/user/change-password/', data),
}
