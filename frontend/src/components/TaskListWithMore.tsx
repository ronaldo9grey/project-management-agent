import { useState } from 'react'

interface Task {
  task_id: string
  task_name: string
  status: string
  progress: number
  start_date: string | null
  end_date: string | null
  actual_end_date: string | null
  delay_days: number
  daily_reports?: Array<{
    date: string
    reporter: string
    content: string
  }>
}

interface TaskListWithMoreProps {
  tasks: Task[]
  type: 'delayed' | 'delayed_completed' | 'ongoing' | 'completed'
  initialLimit?: number
}

export default function TaskListWithMore({ tasks, type, initialLimit = 5 }: TaskListWithMoreProps) {
  const [showAll, setShowAll] = useState(false)
  
  const displayTasks = showAll ? tasks : tasks.slice(0, initialLimit)
  const hasMore = tasks.length > initialLimit
  
  const getTaskStyle = () => {
    switch (type) {
      case 'delayed':
        return {
          bg: '#fef2f2',
          border: '1px solid #fecaca',
          nameColor: '#991b1b',
          badge: { bg: '#ef4444', text: '延期' }
        }
      case 'delayed_completed':
        return {
          bg: '#fffbeb',
          border: '1px solid #fde68a',
          nameColor: '#92400e',
          badge: { bg: '#f59e0b', text: '延期完成' }
        }
      case 'ongoing':
        return {
          bg: '#eff6ff',
          border: '1px solid #bfdbfe',
          nameColor: '#1e40af',
          badge: null
        }
      case 'completed':
        return {
          bg: '#f0fdf4',
          border: '1px solid #bbf7d0',
          nameColor: '#166534',
          badge: { bg: '#22c55e', text: '✓' }
        }
    }
  }
  
  const style = getTaskStyle()
  
  if (tasks.length === 0) return null
  
  return (
    <div>
      {displayTasks.map((task) => (
        <div 
          key={task.task_id} 
          className="home-task-card"
          style={{
            background: style.bg,
            border: style.border,
          }}
        >
          <div className="home-task-header">
            <span 
              className="home-task-name"
              style={{ color: style.nameColor }}
            >
              {task.task_name}
            </span>
            {type === 'delayed' && (
              <span className="home-task-badge home-task-badge-red">
                延期 {task.delay_days} 天
              </span>
            )}
            {type === 'delayed_completed' && (
              <span className="home-task-badge home-task-badge-orange">
                延期 {task.delay_days} 天后完成
              </span>
            )}
            {type === 'ongoing' && (
              <span className="home-task-progress-label">{task.progress}%</span>
            )}
            {type === 'completed' && (
              <span style={{ fontSize: '16px', color: '#22c55e' }}>✓</span>
            )}
          </div>
          
          <div className="home-task-date">
            📅 计划: {task.start_date} ~ {task.end_date}
          </div>
          
          {(type === 'delayed_completed' || type === 'completed') && task.actual_end_date && (
            <div className="home-task-date">
              ✅ 实际完成: {task.actual_end_date}
            </div>
          )}
          
          {(type === 'ongoing' || type === 'delayed') && (
            <div className="progress-bar" style={{ height: '6px', marginBottom: '6px' }}>
              <div 
                className="progress-bar-fill" 
                style={{ 
                  width: `${task.progress}%`, 
                  background: type === 'delayed' ? '#ef4444' : '#3b82f6' 
                }} 
              />
            </div>
          )}
          
          {(task.daily_reports?.length || 0) > 0 && (
            <div 
              className="home-task-reports"
              style={{
                background: type === 'delayed_completed' ? '#fefce8' : 
                           type === 'ongoing' ? '#dbeafe' : '#dcfce7'
              }}
            >
              <div 
                className="home-task-reports-title"
                style={{
                  color: type === 'delayed_completed' ? '#854d0e' : 
                         type === 'ongoing' ? '#1e40af' : '#166534'
                }}
              >
                📝 相关日报
              </div>
              {task.daily_reports?.slice(0, 2).map((r, i) => (
                <div 
                  key={i} 
                  className="home-task-report-item"
                  style={{
                    color: type === 'delayed_completed' ? '#713f12' : 
                           type === 'ongoing' ? '#1e3a8a' : '#14532d'
                  }}
                >
                  • {r.date} {r.reporter}: {r.content?.substring(0, 30)}...
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      
      {hasMore && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          style={{
            width: '100%',
            padding: '10px',
            marginTop: '8px',
            background: '#f8fafc',
            border: '1px dashed #cbd5e1',
            borderRadius: '8px',
            color: '#64748b',
            fontSize: '13px',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#f1f5f9'
            e.currentTarget.style.color = '#3b82f6'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#f8fafc'
            e.currentTarget.style.color = '#64748b'
          }}
        >
          📥 加载更多 ({tasks.length - initialLimit} 条)
        </button>
      )}
      
      {showAll && hasMore && (
        <button
          onClick={() => setShowAll(false)}
          style={{
            width: '100%',
            padding: '8px',
            marginTop: '8px',
            background: 'transparent',
            border: 'none',
            color: '#64748b',
            fontSize: '12px',
            cursor: 'pointer'
          }}
        >
          ▲ 收起
        </button>
      )}
    </div>
  )
}
