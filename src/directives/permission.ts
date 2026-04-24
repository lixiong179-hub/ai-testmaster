import { App, Directive, DirectiveBinding } from 'vue'

const PERMISSION_SIGN_KEY = '__perm_sig__'

interface PermissionSignedObject {
  permissions: string[]
  [PERMISSION_SIGN_KEY]?: string
}

interface HTMLElementWithPermission extends HTMLElement {
  __permissionPlaceholder?: Comment
}

function getPermissions(): string[] {
  const userInfo = localStorage.getItem('userInfo')
  if (!userInfo) return []
  try {
    const parsed: PermissionSignedObject = JSON.parse(userInfo)
    if (!parsed.permissions || !Array.isArray(parsed.permissions)) return []
    const sig = parsed[PERMISSION_SIGN_KEY]
    if (!sig || sig !== computeSignature(parsed.permissions)) return []
    return parsed.permissions
  } catch {
    return []
  }
}

function computeSignature(permissions: string[]): string {
  const raw = permissions.slice().sort().join(',')
  let hash = 0
  for (let i = 0; i < raw.length; i++) {
    const ch = raw.charCodeAt(i)
    hash = (hash << 5) - hash + ch
    hash |= 0
  }
  return hash.toString(36)
}

export function signPermissions(permissions: string[]): Record<string, string | string[]> {
  const obj: Record<string, string | string[]> = { permissions }
  obj[PERMISSION_SIGN_KEY] = computeSignature(permissions)
  return obj
}

const permissionDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const permission = binding.value
    if (permission && !getPermissions().includes(permission)) {
      const comment = document.createComment('')
      el.parentNode?.replaceChild(comment, el)
      ;(el as HTMLElementWithPermission).__permissionPlaceholder = comment
    }
  },
  updated(el: HTMLElement, binding: DirectiveBinding) {
    const permission = binding.value
    const hasPermission = !permission || getPermissions().includes(permission)
    const placeholder = (el as HTMLElementWithPermission).__permissionPlaceholder

    if (!hasPermission && el.parentNode) {
      const comment = document.createComment('')
      el.parentNode.replaceChild(comment, el)
      ;(el as HTMLElementWithPermission).__permissionPlaceholder = comment
    } else if (hasPermission && placeholder && placeholder.parentNode) {
      placeholder.parentNode.replaceChild(el, placeholder)
      delete (el as HTMLElementWithPermission).__permissionPlaceholder
    }
  },
}

export const registerPermissionDirective = (app: App) => {
  app.directive('permission', permissionDirective)
}
