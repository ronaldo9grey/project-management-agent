import { useState } from 'react'

interface Task {
  task_id: string
  task_name: string
  end_date: string | null
  progress: number
}

interface DashboardTaskListProps {
  tasks: Task[]
  getTaskStatus: (progress: number, endDate: string | null) => string
  formatDate: (date: string | null) => string
}

export default function DashboardTaskList({ tasks, getTaskStatus, formatDate }: DashboardTaskListProps) {
  const [showAll, setShowAll] = useState(false)
  
  const filteredTasks = tasks.filter(task => {
    const endDate = task.end_date ? new Date(task.end_date) : null
    if (!endDate) return false
    const today = new Date()
    const weekLater = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)
    return endDate <= weekLater || task.progress < 100
  })
  
  const displayTasks = showAll ? filteredTasks : filteredTasks.slice(0, 5)
  
  if (filteredTasks.length === 0) return null
  
  return (
    <>
      {displayTasks.map(task => {
        const status = getTaskStatus(task.progress, task.end_date)
        return (
          <div key={task.task_id} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px',
            background: status === 'completed' ? '#f0fdf4' : status === 'delayed' ? '#fef2f2' : '#eff6ff',
            borderRadius: '6px',
            fontSize: '12px'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: status === 'completed' ? '#22c55e' : status === 'delayed' ? '#ef4444' : '#3b82f6'
            }} />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {task.task_name}
            </span>
            <span style={{ color: '#666' }}>{formatDate(task.end_date)}</span>
            <span style={{ fontWeight: 500 }}>{task.progress}%</span>
          </div>
        )
      })}
      {filteredTasks.length > 5 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          style={{
            width: '100%',
            padding: '8px',
            background: '#f8fafc',
            border: '1px dashed #cbd5e1',
            borderRadius: '6px',
            color: '#64748b',
            fontSize: '12px',
            cursor: 'pointer'
          }}
        >
          📥 加载更多 ({filteredTasks.length - 5} 条)
        </button>
      )}
      {showAll && filteredTasks.length > 5 && (
        <button
          onClick={() => setShowAll(false)}
          style={{
            width: '100%',
            padding: '6px',
            background: 'transparent',
            border: 'none',
            color: '#64748b',
            fontSize: '11px',
            cursor: 'pointer'
          }}
        >
          ▲ 收起
        </button>
      )}
    </>
  )
}
