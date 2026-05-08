/**
 * 请求工具 - 支持取消、重试、超时
 */

// 请求缓存
const requestCache = new Map<string, { data: any; timestamp: number }>()
const CACHE_TTL = 30000 // 30秒缓存

// 请求取消控制器
const pendingRequests = new Map<string, AbortController>()

// 请求配置
interface RequestOptions {
  cache?: boolean
  cacheKey?: string
  timeout?: number
  retry?: number
}

/**
 * 带缓存的请求
 */
export async function fetchWithCache(
  url: string,
  options: RequestInit = {},
  config: RequestOptions = {}
): Promise<any> {
  const { cache = true, cacheKey, timeout = 30000, retry = 1 } = config
  
  // 检查缓存
  const key = cacheKey || url
  if (cache) {
    const cached = requestCache.get(key)
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data
    }
  }
  
  // 取消之前的相同请求
  const pendingKey = `${options.method || 'GET'}:${key}`
  const existingController = pendingRequests.get(pendingKey)
  if (existingController) {
    existingController.abort()
  }
  
  // 创建新的取消控制器
  const controller = new AbortController()
  pendingRequests.set(pendingKey, controller)
  
  // 超时处理
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  
  try {
    const token = localStorage.getItem('project-agent-storage')
      ? JSON.parse(localStorage.getItem('project-agent-storage') || '{}')?.state?.token
      : null
    
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    
    const data = await response.json()
    
    // 缓存结果
    if (cache) {
      requestCache.set(key, { data, timestamp: Date.now() })
    }
    
    return data
    
  } catch (error: any) {
    clearTimeout(timeoutId)
    
    // 如果是取消请求，不重试
    if (error.name === 'AbortError') {
      console.log(`请求已取消: ${url}`)
      throw error
    }
    
    // 重试
    if (retry > 0) {
      console.log(`请求失败，重试 ${retry} 次: ${url}`)
      return fetchWithCache(url, options, { ...config, retry: retry - 1 })
    }
    
    throw error
  } finally {
    pendingRequests.delete(pendingKey)
  }
}

/**
 * 取消所有未完成的请求
 */
export function cancelAllRequests() {
  pendingRequests.forEach((controller) => {
    controller.abort()
  })
  pendingRequests.clear()
}

/**
 * 取消特定请求
 */
export function cancelRequest(method: string, url: string) {
  const key = `${method}:${url}`
  const controller = pendingRequests.get(key)
  if (controller) {
    controller.abort()
    pendingRequests.delete(key)
  }
}

/**
 * 清除缓存
 */
export function clearCache(key?: string) {
  if (key) {
    requestCache.delete(key)
  } else {
    requestCache.clear()
  }
}

/**
 * 防抖请求
 */
export function debounceRequest<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  delay: number = 300
): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  let lastController: AbortController | null = null
  
  return ((...args: Parameters<T>) => {
    // 取消之前的请求
    if (lastController) {
      lastController.abort()
    }
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    lastController = new AbortController()
    
    return new Promise((resolve, reject) => {
      timeoutId = setTimeout(async () => {
        try {
          const result = await fn(...args)
          resolve(result)
        } catch (error) {
          reject(error)
        }
      }, delay)
    })
  }) as T
}

/**
 * 节流请求
 */
export function throttleRequest<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  limit: number = 1000
): T {
  let inProgress = false
  let lastPromise: Promise<any> | null = null
  
  return ((...args: Parameters<T>) => {
    if (inProgress && lastPromise) {
      return lastPromise
    }
    
    inProgress = true
    lastPromise = fn(...args).finally(() => {
      setTimeout(() => {
        inProgress = false
      }, limit)
    })
    
    return lastPromise
  }) as T
}
