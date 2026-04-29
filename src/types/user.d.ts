// 用户与权限相关类型声明

// 用户信息
export interface User {
  id: number;
  username: string;
  email: string;
  phone: string;
  status: boolean;
  last_login_time: string | null;
  created_at: string;
  roles?: Role[];
}

// 角色信息
export interface Role {
  id: number;
  name: string;
  desc: string;
  permissions: string[];
  created_at: string;
}

// 权限信息
export interface Permission {
  id: number;
  name: string;
  code: string;
  type: 'menu' | 'button' | 'api';
  parent_id: number | null;
  created_at: string;
}

// 登录表单
export interface LoginForm {
  username: string;
  password: string;
  code: string;
  remember: boolean;
}

// 登录响应
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// 用户创建/更新表单
export interface UserForm {
  username: string;
  email: string;
  phone: string;
  password?: string;
  status: boolean;
}

// 角色创建/更新表单
export interface RoleForm {
  name: string;
  desc: string;
  permissions: string[];
}

// 权限创建/更新表单
export interface PermissionForm {
  name: string;
  code: string;
  type: 'menu' | 'button' | 'api';
  parent_id: number | null;
}

// 分页参数
export interface Pagination {
  page: number;
  size: number;
  total: number;
}

// 分页响应
export interface PageResponse<T> {
  data: T[];
  pagination: Pagination;
}

// 菜单配置
export interface MenuItem {
  id: string;
  label: string;
  path: string;
  icon?: string;
  children?: MenuItem[];
  permission?: string;
}
