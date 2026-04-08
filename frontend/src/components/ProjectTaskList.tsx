import { useState } from 'react'

interface Task {
  task_id: string
  task_name: string
  status: string
  progress?: number
  start_date?: string | null
  end_date?: string | null
  planned_hours?: number
  assignee?: string
  daily_reports?: Array<{
    report_date: string
    work_content: string
    hours_spent: number
  }>
}

interface ProjectTaskListProps {
  tasks: Task[]
  initialLimit?: number
  expandedTasks: Set<string>
  onToggleTask: (taskId: string) => void
}

export default function ProjectTaskList({ 
  tasks, 
  initialLimit = 5, 
  expandedTasks,
  onToggleTask 
}: ProjectTaskListProps) {
  const [showAll, setShowAll] = useState(false)
  
  const displayTasks = showAll ? tasks : tasks.slice(0, initialLimit)
  const hasMore = tasks.length > initialLimit
  
  if (tasks.length === 0) return null
  
  return (
    <div className="task-phase-items">
      {displayTasks.map((task) => {
        const isTaskExpanded = expandedTasks.has(task.task_id)
        
        return (
          <div key={task.task_id} className="task-item">
            <div className="task-main">
              <div 
                className="task-header"
                style={{cursor: (task.daily_reports?.length || 0) > 0 ? 'pointer' : 'default'}}
                onClick={() => {
                  if ((task.daily_reports?.length || 0) > 0) {
                    onToggleTask(task.task_id)
                  }
                }}
              >
                <span className="task-name">
                  {(task.daily_reports?.length || 0) > 0 && (
                    <span style={{
                      marginRight: '6px',
                      transform: isTaskExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s',
                      display: 'inline-block',
                      fontSize: '10px'
                    }}>▶</span>
                  )}
                  {task.task_name}
                </span>
                <span className={`task-status ${task.status === '已完成' ? 'done' : task.status === '延期' ? 'delayed' : task.status === '进行中' ? 'active' : ''}`}>
                  {task.status}
                </span>
              </div>
              <div className="task-meta">
                {task.assignee && <span>👤 {task.assignee}</span>}
                {task.start_date && task.end_date && (
                  <span>📅 {task.start_date} ~ {task.end_date}</span>
                )}
                {task.planned_hours && <span>⏱ {task.planned_hours}h</span>}
              </div>
              <div className="task-progress">
                <div className="progress-bar-sm">
                  <div className="progress-bar-fill" style={{ width: `${task.progress || 0}%` }} />
                </div>
                <span className="progress-text">{task.progress?.toFixed(1) || 0}%</span>
              </div>
            </div>
            
            {isTaskExpanded && (task.daily_reports?.length || 0) > 0 && (
              <div className="task-daily-reports">
                <div style={{
                  fontSize: '12px',
                  color: '#64748b',
                  marginBottom: '8px',
                  fontWeight: '500'
                }}>
                  📝 关联日报（{(task.daily_reports?.length || 0)} 条）
                </div>
                {task.daily_reports && (task.daily_reports || []).map((report, idx) => (
                  <div key={idx} className="daily-report-item">
                    <span className="report-date">{report.report_date}</span>
                    <span className="report-content">{report.work_content}</span>
                    <span className="report-hours">{report.hours_spent}h</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
      
      {hasMore && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          style={{
            width: '100%',
            padding: '12px',
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
          📥 加载更多 ({tasks.length - initialLimit} 条任务)
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
