import { useState, useEffect } from 'react'
import { dashboardApi } from '../api'

interface SmartAssistantData {
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

export default function SmartAssistant() {
  const [data, setData] = useState<SmartAssistantData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const result = await dashboardApi.getSmartAssistant()
      setData(result)
    } catch (error) {
      console.error('加载智能助手数据失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="card">
        <div className="card-body" style={{ padding: '20px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '24px', height: '24px', margin: '0 auto' }}></div>
          <p className="text-gray-500 mt-2">智能分析中...</p>
        </div>
      </div>
    )
  }

  if (!data) return null

  // 获取建议的图标和颜色
  const getSuggestionStyle = (type: string) => {
    switch (type) {
      case 'urgent':
        return { icon: '🔴', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.08)' }
      case 'delayed':
        return { icon: '⚠️', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.08)' }
      case 'report':
        return { icon: '📝', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.08)' }
      case 'hours':
        return { icon: '⏱️', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.08)' }
      default:
        return { icon: '💡', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.08)' }
    }
  }

  return (
    <div className="space-y-4">
      {/* 智能建议卡片 - 清新风格 */}
      {data.suggestions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">💡 智能建议</h2>
            <span className="tag tag-info" style={{fontSize: '11px'}}>{data.suggestions.length} 条</span>
          </div>
          <div className="card-body">
            <div className="space-y-3">
              {data.suggestions.map((s, idx) => {
                const style = getSuggestionStyle(s.type)
                return (
                  <div 
                    key={idx}
                    style={{ 
                      padding: '14px 16px',
                      background: style.bg,
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '12px',
                      border: `1px solid ${style.color}20`
                    }}
                  >
                    <span style={{ fontSize: '20px', lineHeight: 1 }}>{style.icon}</span>
                    <div style={{ flex: 1 }}>
                      <span style={{ 
                        fontSize: '14px', 
                        lineHeight: '1.6', 
                        color: '#1e293b',
                        fontWeight: '500'
                      }}>{s.message}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* 今日优先任务 */}
      {data.priority_tasks.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">📌 今日优先</h2>
            <span className="tag tag-primary">{data.priority_tasks.length} 项</span>
          </div>
          <div className="card-body">
            <div className="space-y-3">
              {data.priority_tasks.map((task, idx) => (
                <div 
                  key={task.task_id}
                  className="list-item"
                  style={{ 
                    borderLeft: `3px solid ${
                      task.urgency === 'urgent' ? '#ef4444' : 
                      task.urgency === 'high' ? '#f59e0b' : '#3b82f6'
                    }`
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <span style={{ 
                      width: '24px', 
                      height: '24px', 
                      borderRadius: '50%', 
                      background: '#f3f4f6',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '12px',
                      fontWeight: 'bold',
                      color: '#6b7280'
                    }}>
                      {idx + 1}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span className="font-medium text-gray-900">{task.task_name}</span>
                        <span className={`tag ${
                          task.urgency === 'urgent' ? 'tag-danger' : 
                          task.urgency === 'high' ? 'tag-warning' : 'tag-default'
                        }`} style={{ fontSize: '11px' }}>
                          {task.urgency_label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">📁 {task.project_name}</p>
                      <p className="text-xs text-blue-600 mt-1" style={{ fontStyle: 'italic' }}>
                        💡 {task.suggestion}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 延期预警详情 */}
      {data.delayed_warnings.length > 0 && (
        <div className="card" style={{ borderColor: '#ef4444' }}>
          <div className="card-header">
            <h2 className="card-title" style={{ color: '#ef4444' }}>⚠️ 延期预警</h2>
            <span className="tag tag-danger">{data.delayed_warnings.length} 项</span>
          </div>
          <div className="card-body">
            <div className="space-y-2">
              {data.delayed_warnings.slice(0, 3).map((task) => (
                <div 
                  key={task.task_id}
                  style={{ 
                    padding: '10px',
                    background: 'rgba(239, 68, 68, 0.05)',
                    borderRadius: '8px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span className="font-medium text-gray-900">{task.task_name}</span>
                      <p className="text-sm text-gray-500 mt-1">📁 {task.project_name}</p>
                    </div>
                    <span className="tag tag-danger">延期 {task.delay_days} 天</span>
                  </div>
                  <p className="text-xs text-red-600 mt-2">💡 {task.suggestion}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
