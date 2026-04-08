import axios, { AxiosError, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
import { useAppStore } from './store'
import { showToast } from './components/Toast'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/agent-api'

function showErrorMessage(message: string) {
  console.error('[API Error]', message)
  showToast(message, 'error')
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token 刷新相关
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function subscribeTokenRefresh(callback: (token: string) => void) {
  refreshSubscribers.push(callback)
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach(callback => callback(token))
  refreshSubscribers = []
}

// 检查 token 是否即将过期（提前 30 分钟刷新）
function isTokenExpiringSoon(): boolean {
  const storage = localStorage.getItem('project-agent-storage')
  if (!storage) return false
  
  try {
    const data = JSON.parse(storage)
    const token = data.state?.token
    if (!token) return false
    
    // 解析 JWT payload（不验证签名，只看时间）
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = payload.exp * 1000 // 转毫秒
    const now = Date.now()
    const thirtyMinutes = 30 * 60 * 1000
    
    // 如果 30 分钟内过期，返回 true
    return (exp - now) < thirtyMinutes
  } catch {
    return false
  }
}

// 请求拦截器 - 添加token + 自动刷新
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = useAppStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
    
    // 检查是否需要刷新 token（排除刷新接口本身）
    if (!config.url?.includes('/auth/refresh') && !config.url?.includes('/auth/login') && isTokenExpiringSoon()) {
      try {
        const res = await axios.post(`${API_BASE_URL}/api/agent/auth/refresh`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        })
        const newToken = res.data.access_token
        if (newToken) {
          // 更新 store 和 localStorage
          useAppStore.getState().setToken(newToken)
          config.headers.Authorization = `Bearer ${newToken}`
          console.log('[Auth] Token 自动刷新成功')
        }
      } catch (e) {
        console.warn('[Auth] Token 刷新失败，继续使用当前 token', e)
      }
    }
  }
  return config
})

// 响应拦截器 - 处理错误 + 请求重试
const BASE_PATH = '/agent'
const MAX_RETRY = 1

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: number }
    
    // 排除登录接口的 401 处理
    const isLoginRequest = error.config?.url?.includes('/auth/login')
    const isRefreshRequest = error.config?.url?.includes('/auth/refresh')
    
    if (error.response?.status === 401 && !isLoginRequest) {
      // 如果是刷新接口 401，直接登出
      if (isRefreshRequest) {
        useAppStore.getState().logout()
        window.location.href = `${BASE_PATH}/login`
        return Promise.reject(error)
      }
      
      // 尝试刷新 token
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const token = useAppStore.getState().token
          const res = await axios.post(`${API_BASE_URL}/api/agent/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${token}` }
          })
          const newToken = res.data.access_token
          if (newToken) {
            useAppStore.getState().setToken(newToken)
            onTokenRefreshed(newToken)
            isRefreshing = false
            
            // 重试原请求
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            return apiClient(originalRequest)
          }
        } catch (refreshError) {
          isRefreshing = false
          useAppStore.getState().logout()
          window.location.href = `${BASE_PATH}/login`
          return Promise.reject(refreshError)
        }
      } else {
        // 正在刷新，等待刷新完成后重试
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(apiClient(originalRequest))
          })
        })
      }
    }
    
    // 网络错误重试
    if (!error.response && (originalRequest._retry === undefined || originalRequest._retry < MAX_RETRY)) {
      originalRequest._retry = (originalRequest._retry || 0) + 1
      console.log(`[Network] 请求失败，重试 ${originalRequest._retry}/${MAX_RETRY}`)
      await new Promise(r => setTimeout(r, 1000)) // 等待 1 秒
      return apiClient(originalRequest)
    }
    
    // 网络错误提示（重试失败后）
    if (!error.response) {
      showErrorMessage('网络连接失败，请检查网络后刷新页面重试')
    }
    
    // 服务器错误提示
    if (error.response?.status && error.response.status >= 500) {
      showErrorMessage('服务器繁忙，请稍后重试')
    }
    
    return Promise.reject(error)
  }
)

// 日报相关API
export const dailyApi = {
  // 智能解析日报文本（新接口）
  smartParse: async (text: string, reportDate?: string) => {
    const res = await apiClient.post('/api/agent/daily/smart-parse', {
      text,
      report_date: reportDate
    })
    return res.data as {
      entries: Array<{
        start_time: string
        end_time: string
        content: string
        project_hint?: string
        hours: number
        matched_project_id?: number
        matched_project_name?: string
        match_confidence: number
      }>
      matched_projects: Array<{
        id: number
        name: string
        leader: string
        confidence: number
      }>
      unmatched_projects: string[]
      warnings: string[]
      confidence: number
      issues: string[]
    }
  },
  
  // 创建日报（新接口）
  createReport: async (data: {
    report_date: string
    work_items: Array<{
      project_id?: string
      project_name: string
      task_name: string
      work_content: string
      hours_spent: number
      progress_percentage: number
      status: string
      task_id?: string
    }>
    work_target?: string
    tomorrow_plan?: string
    original_input?: string  // 原始自然语言输入
    ai_parsed_data?: any  // AI解析结果
  }) => {
    const res = await apiClient.post('/api/agent/daily/create', data)
    return res.data as { success: boolean; message: string; report_id?: number }
  },
  
  // 获取我的日报列表
  getMyReports: async (page: number = 1, size: number = 10) => {
    const res = await apiClient.get('/api/agent/daily/my-reports', {
      params: { page, size }
    })
    return res.data as {
      items: Array<{
        id: number
        report_date: string
        total_hours: number
        status: string
        created_at: string
        items: Array<{
          work_content: string
          project_name: string
          start_time: string
          end_time: string
          hours_spent: number
        }>
      }>
      total: number
      page: number
      size: number
    }
  },
  
  // 解析日报文本（旧接口，保留兼容）
  parse: async (text: string) => {
    // 使用新的智能解析接口
    const result = await dailyApi.smartParse(text)
    return {
      entries: result.entries,
      confidence: result.confidence,
      issues: result.issues
    }
  },
  
  // 提交日报（旧接口，保留兼容）
  submit: async (date: string, entries: unknown[]) => {
    // 转换为新的格式
    const workItems = (entries as Array<{
      content: string
      hours: number
      matched_project_id?: number
      matched_project_name?: string
      project_hint?: string
    }>).map(e => ({
      project_id: e.matched_project_id?.toString(),
      project_name: e.matched_project_name || e.project_hint || '',
      task_name: e.content.slice(0, 50),
      work_content: e.content,
      hours_spent: e.hours,
      progress_percentage: 0,
      status: '进行中'
    }))
    
    return dailyApi.createReport({
      report_date: date,
      work_items: workItems
    })
  },
}

// 项目相关API
export const projectApi = {
  // 获取我的项目列表
  getMyProjects: async () => {
    const res = await apiClient.get('/api/agent/projects')
    return res.data as Array<{
      id: number
      name: string
      leader: string
      status: string
      progress: number
    }>
  },
  
  // 获取项目详情
  getProjectDetail: async (projectId: number) => {
    const res = await apiClient.get(`/api/agent/projects/${projectId}`)
    return res.data as {
      id: number
      name: string
      leader: string
      status: string
      progress: number
      description?: string
      start_date?: string
      end_date?: string
      budget?: number
      contract_amount?: number
      project_category?: string
      project_subject?: string
      implementation_mode?: string
      project_level?: string
      total_hours: number
      worker_hours: Array<{ name: string; hours: number }>
    }
  },
  
  // 获取项目任务
  getTasks: async (projectId: number) => {
    const res = await apiClient.get(`/api/agent/projects/${projectId}/tasks`)
    return res.data as Array<{
      task_id: string
      task_name: string
      assignee?: string
      start_date?: string
      end_date?: string
      status: string
      progress?: number
    }>
  },
  
  // 获取项目风险雷达
  getRiskRadar: async (projectId: number) => {
    const res = await apiClient.get(`/api/agent/projects/${projectId}/risk-radar`)
    return res.data as {
      project_id: number
      radar: {
        schedule_risk: number
        material_risk: number
        outsourcing_risk: number
        labor_risk: number
        indirect_risk: number
      }
      overall_risk: number
      risk_level: string
      risk_label: string
      details: {
        total_tasks: number
        delayed_tasks: number
        completed_tasks: number
        days_remaining: number | null
        remaining_tasks: number
        cost_details: {
          material: { budget: number; actual: number }
          outsourcing: { budget: number; actual: number }
          labor: { budget: number; actual: number }
          indirect: { budget: number; actual: number }
        }
      }
    }
  },
  
  // 获取任务风险预警
  getTaskRisks: async (projectId: number) => {
    const res = await apiClient.get(`/api/agent/projects/${projectId}/task-risks`)
    return res.data as {
      project_id: number
      risks: Array<{
        task_id: string
        task_name: string
        risk_type: string
        risk_level: string
        message: string
        delay_days?: number
        remaining_days?: number
        days_since_start?: number
        days_to_start?: number
        progress?: number
      }>
      risk_count: number
      high_risk_count: number
      medium_risk_count: number
      low_risk_count: number
    }
  },
}

// 认证API
export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    
    const res = await apiClient.post('/api/agent/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
    return res.data as { access_token: string; token_type: string; user?: { id: string; name: string; username: string; role_id?: number } }
  },
  
  // 获取用户信息
  getUserInfo: async () => {
    const res = await apiClient.get('/api/agent/auth/me')
    return res.data as {
      id: string
      employee_id: string
      name: string
      username: string
      department?: string
      position?: string
      phone?: string
      email?: string
      role_id?: number
      role_name?: string
      permissions?: {
        allowed_modules?: string[]
        allowed_routes?: string[]
      }
    }
  }
}

// 工时统计API
export const statsApi = {
  // 获取工时统计
  getWorkHoursStats: async () => {
    const res = await apiClient.get('/api/agent/work-hours/stats')
    return res.data as {
      today: number
      week: number
      month: number
      projects: Array<{
        name: string
        hours: number
        percent: number
      }>
    }
  },
  
  // 获取工时趋势
  getHoursTrend: async (timeRange: 'week' | 'month' = 'week') => {
    const res = await apiClient.get(`/api/agent/stats/hours-trend`, {
      params: { time_range: timeRange }
    })
    return res.data as {
      dates: string[]
      actual: number[]
      predicted: number[]
    }
  },
  
  // 获取项目工时分布
  getProjectDistribution: async () => {
    const res = await apiClient.get('/api/agent/stats/project-distribution')
    return res.data as Array<{ name: string; value: number }>
  },
  
  // 获取团队工时统计（项目负责人视角）
  getTeamWorkHours: async () => {
    const res = await apiClient.get('/api/agent/stats/team-work-hours')
    return res.data as Array<{
      project_name: string
      members: Array<{
        name: string
        hours: number
        percent: number
      }>
      total_hours: number
    }>
  }
}

// 今日聚焦API
export const dashboardApi = {
  // 获取今日聚焦数据
  getTodayFocus: async () => {
    const res = await apiClient.get('/api/agent/dashboard/today-focus')
    return res.data as {
      today_tasks: Array<{
        task_id: string
        task_name: string
        project_id: string
        project_name: string
        start_date: string | null
        end_date: string | null
        status: string
        progress: number
      }>
      delayed_tasks: Array<{
        task_id: string
        task_name: string
        project_id: string
        project_name: string
        start_date: string | null
        end_date: string | null
        delay_days: number
        status: string
        progress: number
      }>
      month_goals: Array<{
        id: number
        title: string
        progress_rate: number
        status: string
      }>
      daily_report_status: {
        submitted: boolean
        report_id: number | null
        status: string | null
      }
      week_overview: {
        report_count: number
        total_hours: number
        project_count: number
      }
      date: string
      employee_name: string
    }
  },
  
  // 获取风险预警（管理员）
  getRiskAlerts: async () => {
    const res = await apiClient.get('/api/agent/dashboard/risk-alerts')
    return res.data as {
      delayed_projects: Array<{
        project_id: number
        project_name: string
        leader: string
        delayed_count: number
        max_delay_days: number
      }>
      unreported_users: Array<{
        employee_id: string
        name: string
        department: string
      }>
      high_risk_projects: Array<{
        project_id: number
        project_name: string
        leader: string
        total_tasks: number
        delayed_tasks: number
        delay_rate: number
      }>
      is_admin: boolean
    }
  },
  
  // 获取我负责的项目风险
  getMyProjectRisks: async () => {
    const res = await apiClient.get('/api/agent/dashboard/my-project-risks')
    return res.data as Array<{
      project_id: number
      project_name: string
      leader: string
      delayed_count: number
      max_delay_days: number
      total_tasks: number
      delayed_tasks: number
      delay_rate: number
    }>
  },
  
  // 获取项目看板数据
  getProjectBoard: async () => {
    const res = await apiClient.get('/api/agent/dashboard/project-board')
    return res.data as {
      projects: Array<{
        id: number
        name: string
        leader: string
        status: string
        progress: number
        risk_level: string
        delayed_tasks: number
        total_tasks: number
      }>
    }
  },
  
  // 获取风险矩阵
  getRiskMatrix: async () => {
    const res = await apiClient.get('/api/agent/dashboard/risk-matrix')
    return res.data as {
      projects: Array<{
        project_id: number
        project_name: string
        schedule_risk: number
        resource_risk: number
        overall_risk: number
      }>
    }
  },
  
  // 获取智能助手数据
  getSmartAssistant: async () => {
    const res = await apiClient.get('/api/agent/dashboard/smart-assistant')
    return res.data as {
      priority_tasks: Array<{
        task_id: string
        task_name: string
        project_id: string
        project_name: string
        end_date: string | null
        status: string
        progress: number
        urgency: string
        urgency_label: string
        suggestion: string
      }>
      delayed_warnings: Array<{
        task_id: string
        task_name: string
        project_name: string
        delay_days: number
        progress: number
        suggestion: string
      }>
      hours_prediction: {
        current_hours: number
        predicted_hours: number
        warning_line: number
        is_warning: boolean
        status: string
        suggestion: string
      }
      suggestions: Array<{
        type: string
        priority: number
        message: string
      }>
      daily_report_status: {
        submitted: boolean
        report_id?: number
        status?: string
        suggestion?: string
      }
    }
  }
}

// 项目相关API（别名）
export const projectsApi = {
  getList: async () => {
    const res = await apiClient.get('/api/agent/projects')
    return res.data as Array<{
      id: number
      name: string
      leader: string
      status: string
      progress: number
    }>
  }
}

// 计划相关API
export const plansApi = {
  // 上传计划Excel
  uploadPlan: async (projectId: number, file: File, versionName?: string, description?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const params = new URLSearchParams()
    if (versionName) params.append('version_name', versionName)
    if (description) params.append('description', description)
    
    const url = `/api/agent/plans/upload/${projectId}${params.toString() ? '?' + params.toString() : ''}`
    
    const res = await apiClient.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data as {
      success: boolean
      message: string
      version_id?: number
      version_number?: string
      version_name?: string
      task_count?: number
      tasks?: any[]
    }
  },
  
  // 获取项目的版本列表
  getVersions: async (projectId: number) => {
    const res = await apiClient.get(`/api/agent/plans/versions/${projectId}`)
    return res.data as Array<{
      id: number
      project_id: number
      version_number: string
      version_name: string
      description: string | null
      upload_by: string | null
      upload_time: string
      file_name: string | null
      task_count: number
      is_current: boolean
    }>
  },
  
  // 对比两个版本
  compareVersions: async (versionId1: number, versionId2: number) => {
    const res = await apiClient.get(`/api/agent/plans/compare/${versionId1}/${versionId2}`)
    return res.data as {
      version1: { id: number; version_number: string; version_name: string; task_count: number }
      version2: { id: number; version_number: string; version_name: string; task_count: number }
      added_tasks: Array<{
        task_name: string
        assignee: string | null
        start_date: string | null
        end_date: string | null
        planned_hours: number
        status: string
      }>
      deleted_tasks: Array<{
        task_name: string
        assignee: string | null
        start_date: string | null
        end_date: string | null
        planned_hours: number
        status: string
      }>
      modified_tasks: Array<{
        task_name: string
        old_value: any
        new_value: any
        changes: string[]
      }>
      summary: {
        total_changes: number
        added_count: number
        deleted_count: number
        modified_count: number
      }
      ai_analysis: string
    }
  }
}

// 兼容旧的 planApi
export const planApi = {
  upload: async (projectId: number, file: File) => {
    return plansApi.uploadPlan(projectId, file)
  },
}

// 对话API
export const chatApi = {
  chat: async (message: string) => {
    const res = await apiClient.post('/api/agent/chat', { message })
    return res.data as { response: string }
  },
}

// 通知API
export const notificationApi = {
  getList: async (unreadOnly: boolean = false, limit: number = 20) => {
    const res = await apiClient.get('/api/agent/notifications', {
      params: { unread_only: unreadOnly, limit }
    })
    return res.data as {
      notifications: Array<{
        id: number
        type: string
        priority: string
        title: string
        content: string
        is_read: boolean
        create_time: string
        related_task_id: string | null
      }>
      unread_count: number
    }
  },
  
  markRead: async (notificationId: number) => {
    const res = await apiClient.post(`/api/agent/notifications/${notificationId}/read`)
    return res.data as { success: boolean; message: string }
  },
  
  markAllRead: async () => {
    const res = await apiClient.post('/api/agent/notifications/read-all')
    return res.data as { success: boolean; message: string }
  },
  
  generate: async () => {
    const res = await apiClient.post('/api/agent/notifications/generate')
    return res.data as { success: boolean; notifications_created: string[]; count: number }
  }
}

// 周报API
export const reportApi = {
  getWeekly: async (weekStart?: string) => {
    const params = weekStart ? { week_start: weekStart } : {}
    const res = await apiClient.get('/api/agent/reports/weekly', { params })
    return res.data as {
      success: boolean
      employee_name: string
      week_range: {
        start: string
        end: string
        week_number: number
      }
      statistics: {
        report_count: number
        total_hours: number
        project_count: number
        task_count: number
        completed_count: number
        delayed_count: number
      }
      project_hours: Array<{ project_name: string; hours: number; item_count: number }>
      work_summary: Array<{ project_name: string; contents: string; hours: number }>
      tasks: Array<{ task_name: string; project_name: string; status: string; progress: number }>
      delayed_tasks: Array<{ task_name: string; project_name: string; delay_days: number }>
      goals: Array<{ title: string; progress_rate: number }>
      report_markdown: string
    }
  }
}

// 导出API
export const exportApi = {
  getHoursExcel: async (month?: string) => {
    const res = await apiClient.get('/api/agent/export/hours-excel', { params: { month } })
    return res.data
  }
}

// 预测API
export const predictApi = {
  getMonthHours: async () => {
    const res = await apiClient.get('/api/agent/predict/hours')
    return res.data
  }
}

// 团队API
export const teamApi = {
  getHoursRanking: async (month?: string) => {
    const res = await apiClient.get('/api/agent/team/hours-ranking', { params: { month } })
    return res.data
  },
  getGoalsProgress: async () => {
    const res = await apiClient.get('/api/agent/team/goals-progress')
    return res.data
  }
}

// 公共看板API (扩展原有 dashboardApi)
export const boardApi = {
  // 获取看板概览
  getOverview: async () => {
    const res = await apiClient.get('/api/agent/dashboard/overview')
    return res.data as {
      stats: {
        ongoing_projects: number
        completed_projects: number
        total_projects: number
        high_alerts: number
        medium_alerts: number
        low_alerts: number
        total_alerts: number
      }
      health_ranking: Array<{
        id: number
        name: string
        leader: string
        health_score: number
        progress_score: number
        cost_score: number
        risk_score: number
      }>
      recent_alerts: Array<{
        id: number
        project_id: number
        project_name: string
        alert_type: string
        severity: string
        title: string
        content: string
        created_at: string
        is_resolved: boolean
      }>
    }
  },

  // 获取项目列表
  getProjects: async () => {
    const res = await apiClient.get('/api/agent/dashboard/projects')
    return res.data as Array<{
      id: number
      name: string
      leader: string
      status: string
      progress: number
      health_score: number
      delayed_tasks: number
    }>
  },

  // 获取预警列表
  getAlerts: async (severity?: string, projectId?: number) => {
    const params: any = {}
    if (severity) params.severity = severity
    if (projectId) params.project_id = projectId
    const res = await apiClient.get('/api/agent/dashboard/alerts', { params })
    return res.data as Array<{
      id: number
      project_id: number
      project_name: string
      alert_type: string
      severity: string
      title: string
      content: string
      details: any
      created_at: string
      is_resolved: boolean
      resolved_at: string | null
    }>
  },

  // 处理预警
  resolveAlert: async (alertId: number) => {
    const res = await apiClient.post(`/api/agent/dashboard/alerts/${alertId}/resolve`)
    return res.data as { success: boolean; message: string }
  },

  // 获取AI洞察
  getInsight: async () => {
    const res = await apiClient.get('/api/agent/dashboard/insight')
    return res.data as { content: string; cached: boolean }
  },

  // 获取健康度趋势
  getHealthTrend: async (projectId: number, days: number = 30) => {
    const res = await apiClient.get(`/api/agent/dashboard/health/${projectId}/trend`, {
      params: { days }
    })
    return res.data as {
      project_id: number
      period_days: number
      trend: Array<{
        date: string
        health_score: number
        progress_score: number
        cost_score: number
        risk_score: number
        task_total: number
        task_completed: number
        task_delayed: number
        cost_overrun_pct: number
      }>
    }
  },

  // 获取预警规则（admin）
  getAlertRules: async () => {
    const res = await apiClient.get('/api/agent/dashboard/alert-rules')
    return res.data as Array<{
      id: number
      alert_type: string
      alert_name: string
      enabled: boolean
      thresholds: any
      description: string
    }>
  },

  // 更新预警规则（admin）
  updateAlertRule: async (ruleId: number, data: { enabled?: boolean; thresholds?: any }) => {
    const res = await apiClient.put(`/api/agent/dashboard/alert-rules/${ruleId}`, null, {
      params: data
    })
    return res.data as { success: boolean; message: string }
  },

  // 手动触发检测（admin）
  runDetection: async () => {
    const res = await apiClient.post('/api/agent/dashboard/run-detection')
    return res.data as { success: boolean; message: string }
  },

  // 测试推送（admin）
  testPush: async () => {
    const res = await apiClient.post('/api/agent/dashboard/test-push')
    return res.data as { success: boolean; message: string }
  }
}
