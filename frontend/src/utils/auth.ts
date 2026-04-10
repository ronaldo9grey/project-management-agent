/**
 * 认证工具函数 - 统一管理登录/登出/跳转
 */

const BASE_PATH = '/agent'

/**
 * 安全跳转 - 避免在错误页面触发跨域问题
 */
export function safeRedirect(path: string): void {
  console.log('[Auth] safeRedirect called, path:', path)
  console.log('[Auth] current location:', window.location.href)
  console.log('[Auth] current protocol:', window.location.protocol)
  
  // 检查当前协议是否正常
  if (window.location.protocol.startsWith('http')) {
    // 使用 replace 避免历史记录堆积
    window.location.replace(path)
  } else {
    // 在错误页面时，尝试恢复到正常页面
    console.warn('[Auth] 当前处于错误页面，延迟跳转')
    setTimeout(() => {
      if (window.location.protocol.startsWith('http')) {
        window.location.replace(path)
      }
    }, 2000)
  }
}

/**
 * 跳转到登录页
 */
export function redirectToLogin(): void {
  console.log('[Auth] redirectToLogin called')
  console.trace('[Auth] redirectToLogin call stack')
  
  // 清除本地存储
  try {
    localStorage.removeItem('project-agent-storage')
  } catch {}
  safeRedirect(`${BASE_PATH}/login`)
}

/**
 * 检查是否已登录
 */
export function isAuthenticated(): boolean {
  try {
    const storage = localStorage.getItem('project-agent-storage')
    console.log('[Auth] isAuthenticated - storage exists:', !!storage)
    
    if (!storage) {
      console.log('[Auth] isAuthenticated - no storage, returning false')
      return false
    }
    
    const data = JSON.parse(storage)
    const token = data.state?.token
    console.log('[Auth] isAuthenticated - token exists:', !!token)
    
    if (!token) {
      console.log('[Auth] isAuthenticated - no token, returning false')
      return false
    }
    
    // 检查 token 是否过期
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = payload.exp * 1000
    const now = Date.now()
    const isValid = now < exp
    
    console.log('[Auth] isAuthenticated - token exp:', new Date(exp).toISOString())
    console.log('[Auth] isAuthenticated - now:', new Date(now).toISOString())
    console.log('[Auth] isAuthenticated - token valid:', isValid)
    
    return isValid
  } catch (e) {
    console.error('[Auth] isAuthenticated - error:', e)
    return false
  }
}

/**
 * 获取当前 token
 */
export function getToken(): string | null {
  try {
    const storage = localStorage.getItem('project-agent-storage')
    if (!storage) return null
    
    const data = JSON.parse(storage)
    return data.state?.token || null
  } catch {
    return null
  }
}

/**
 * 获取 token 过期时间（毫秒）
 */
export function getTokenExpiry(): number | null {
  try {
    const token = getToken()
    if (!token) return null
    
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp * 1000
  } catch {
    return null
  }
}

/**
 * 检查 token 是否即将过期（30 分钟内）
 */
export function isTokenExpiringSoon(): boolean {
  const expiry = getTokenExpiry()
  if (!expiry) return true // 无过期时间视为需要刷新
  
  const thirtyMinutes = 30 * 60 * 1000
  return (expiry - Date.now()) < thirtyMinutes
}

/**
 * 清除登录状态
 */
export function clearAuth(): void {
  try {
    localStorage.removeItem('project-agent-storage')
  } catch {}
}

// 默认导出 isAuthenticated 供 App.tsx 使用
export { isAuthenticated as default } from './auth'
