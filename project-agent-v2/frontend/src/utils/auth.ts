/**
 * 认证工具函数 - 统一管理登录/登出/跳转
 */

const BASE_PATH = '/agent'

/**
 * 安全跳转 - 简化版，不依赖 protocol 判断
 */
export function safeRedirect(path: string): void {
  console.log('[Auth] safeRedirect called, path:', path)
  
  try {
    // 优先使用 replace（不产生历史记录）
    window.location.replace(path)
  } catch (err) {
    // 备用方案
    console.warn('[Auth] replace failed, using href')
    window.location.href = path
  }
}

/**
 * 跳转到登录页
 */
export function redirectToLogin(): void {
  console.log('[Auth] redirectToLogin called')
  
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
    
    if (!storage) {
      return false
    }
    
    const data = JSON.parse(storage)
    const token = data.state?.token
    
    if (!token) {
      return false
    }
    
    // 检查 token 是否过期
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = payload.exp * 1000
    const now = Date.now()
    const isValid = now < exp
    
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
 * 检查 token 是否即将过期（10 分钟内）
 * 从 30 分钟改为 10 分钟，减少刷新频率
 */
export function isTokenExpiringSoon(): boolean {
  const expiry = getTokenExpiry()
  if (!expiry) return true // 无过期时间视为需要刷新
  
  const tenMinutes = 10 * 60 * 1000  // 从 30 分钟改为 10 分钟
  return (expiry - Date.now()) < tenMinutes
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
