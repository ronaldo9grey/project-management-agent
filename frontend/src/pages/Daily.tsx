import { Link } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { dailyApi } from '../api'
import { showToast } from '../components/Toast'
import { confirm } from '../components/ConfirmDialog'

interface ParsedEntry {
  start_time: string
  end_time: string
  location?: string
  content: string
  project_hint?: string
  hours: number
  matched_project_id?: number
  matched_project_name?: string
  matched_task_id?: string  // 新增：匹配的任务ID
  matched_task_name?: string
  match_confidence: number
}

interface HistoryReport {
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
    task_id?: string
    task_name?: string
  }>
  ai_parsed?: boolean  // 是否经过AI解析
  original_input?: string  // 原始输入文本
  ai_parsed_data?: any  // AI解析结果
}

interface ParseWarning {
  type: 'warning' | 'error' | 'info'
  message: string
}

export default function DailyPage() {
  const { user, dailyEntries, addDailyEntry, removeDailyEntry, clearDailyEntries, logout } = useAppStore()
  const [inputText, setInputText] = useState('')
  const [isParsing, setIsParsing] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (showUserMenu && !target.closest('.user-menu-wrapper')) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showUserMenu])
  const [historyReports, setHistoryReports] = useState<HistoryReport[]>([])
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set())  // 展开的日报ID
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [parseWarnings, setParseWarnings] = useState<ParseWarning[]>([])
  const [matchedProjects, setMatchedProjects] = useState<Array<{id: number; name: string; leader: string}>>([])
  const [hasParsed, setHasParsed] = useState(false)  // 是否已解析（避免切换日期时重复清空）
  
  // 使用本地日期，避免 toISOString() 转为 UTC 导致日期偏差
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  
  // 新增：日期选择功能
  const [selectedDate, setSelectedDate] = useState(today)
  const [showDatePicker, setShowDatePicker] = useState(false)
  
  // 获取选中日期已有的日报
  const existingReport = historyReports.find(r => r.report_date === selectedDate)
  
  // 生成可选日期列表（最近30天）
  const getAvailableDates = () => {
    const dates = []
    for (let i = 0; i < 30; i++) {
      const d = new Date()
      d.setDate(d.getDate() - i)
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      const weekDay = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
      dates.push({ date: dateStr, label: `${dateStr} ${weekDay}`, isToday: i === 0, hasReport: historyReports.some(r => r.report_date === dateStr) })
    }
    return dates
  }
  
  // 格式化选中日期显示
  const formatDateDisplay = (dateStr: string) => {
    const d = new Date(dateStr)
    const weekDay = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
    const isToday = dateStr === today
    return `${dateStr} ${weekDay}${isToday ? ' (今天)' : ''}`
  }

  // 加载历史日报
  useEffect(() => {
    loadHistoryReports()
  }, [])
  
  // 日期切换时：如果已解析则保留内容，否则清空
  // 用户可以通过"清除"按钮手动重置
  // useEffect(() => {
  //   if (!hasParsed) {
  //     clearDailyEntries()
  //     setParseWarnings([])
  //     setMatchedProjects([])
  //   }
  // }, [selectedDate, hasParsed])

  const loadHistoryReports = async () => {
    setIsLoadingHistory(true)
    try {
      const result = await dailyApi.getMyReports(1, 10)
      setHistoryReports(result.items || [])
    } catch (error) {
      console.error('加载历史日报失败:', error)
      setHistoryReports([])
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const handleParse = async () => {
    if (!inputText.trim()) return
    
    setIsParsing(true)
    setParseWarnings([])
    setMatchedProjects([])
    
    try {
      const result = await dailyApi.smartParse(inputText, selectedDate)
      
      // 显示警告信息
      if (result.warnings && result.warnings.length > 0) {
        setParseWarnings(result.warnings.map(w => ({
          type: 'warning' as const,
          message: w
        })))
      }
      
      // 记录匹配的项目
      if (result.matched_projects && result.matched_projects.length > 0) {
        setMatchedProjects(result.matched_projects)
      }
      
      // 添加解析结果
      if (result.entries && result.entries.length > 0) {
        // 清空之前的记录（支持多次输入覆盖）
        clearDailyEntries()
        
        result.entries.forEach((entry: ParsedEntry) => {
          addDailyEntry(entry)
        })
        
        // 标记已解析（避免切换日期时清空）
        setHasParsed(true)
        
        // 解析成功，保留输入内容（不清空）
        // setInputText('')  // 已移除：不清空输入框
        
        // 显示成功提示
        setParseWarnings([{
          type: 'info' as const,
          message: `✅ 已解析 ${result.entries.length} 条工作记录${result.matched_projects?.length > 0 ? '，项目已匹配' : ''}`
        }])
      } else {
        // 解析失败，保留输入内容，给出提示
        setParseWarnings([
          { type: 'error' as const, message: '⚠️ 未识别到有效的工作事项，请检查输入格式' },
          { type: 'info' as const, message: '💡 提示：请描述具体的工作内容和时间，例如"上午完成需求归档4小时"' }
        ])
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '解析失败，请重试'
      setParseWarnings([
        { type: 'error' as const, message: `❌ ${errorMsg}` },
        { type: 'info' as const, message: '💡 您可以重新输入或手动添加工作记录' }
      ])
      console.error(error)
      // 解析失败，保留输入内容
    } finally {
      setIsParsing(false)
    }
  }

  const handleSubmit = async () => {
    console.log('[日报提交] 开始提交, dailyEntries:', dailyEntries.length)
    
    if (dailyEntries.length === 0) {
      showToast('请先解析日报内容', 'warning')
      return
    }
    
    // 检查选中日期是否已有日报
    const hasExistingReport = historyReports.some(r => r.report_date === selectedDate)
    console.log('[日报提交] 选中日期是否已有日报:', hasExistingReport, '日期:', selectedDate)
    
    if (hasExistingReport) {
      console.log('[日报提交] 弹出覆盖确认框')
      const confirmed = await confirm({
        title: '确认覆盖该日期日报？',
        message: `${selectedDate} 已经提交过日报，新提交的内容将覆盖之前的记录。`,
        confirmText: '覆盖提交',
        cancelText: '取消',
        type: 'warning'
      })
      console.log('[日报提交] 覆盖确认结果:', confirmed)
      if (!confirmed) return
    }
    
    console.log('[日报提交] 开始调用API')
    showToast(`正在提交 ${selectedDate} 日报...`, 'info')
    setIsSubmitting(true)
    
    try {
      const workItems = dailyEntries.map(entry => ({
        project_id: entry.matched_project_id ? String(entry.matched_project_id) : undefined,
        project_name: entry.matched_project_name || entry.project_hint || '',
        task_id: entry.matched_task_id || undefined,
        task_name: entry.content.substring(0, 50),
        work_content: entry.content,
        hours_spent: entry.hours || 0,
        start_time: entry.start_time || undefined,
        end_time: entry.end_time || undefined,
        progress_percentage: 0,
        status: '进行中'
      }))
      
      await dailyApi.createReport({
        report_date: selectedDate,
        work_items: workItems,
        work_target: '完成日常工作',
        tomorrow_plan: '',
        original_input: inputText,
        ai_parsed_data: {
          entries: dailyEntries,
          warnings: parseWarnings
        }
      })
      
      showToast(`${selectedDate} 日报提交成功！`, 'success')
      setInputText('')
      clearDailyEntries()
      setParseWarnings([])
      setMatchedProjects([])
      setHasParsed(false)  // 提交成功后重置已解析状态
      loadHistoryReports()
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '提交失败，请重试'
      showToast(errorMsg, 'error')
      console.error(error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  const totalHours = dailyEntries.reduce((sum, e) => sum + (e.hours || 0), 0)

  // 示例文本作为 placeholder
  const placeholderText = `示例：今天做了以下工作：

上午 9:00-11:30 在设计院参加600KA槽项目的图纸审查会议

下午 14:00-17:00 在施工现场检查除尘系统改造进度

---
💡 提示：描述中包含时间、地点、项目名、工作内容，AI会自动解析

🎤 手机用户：点击输入框后，使用输入法的语音功能更稳定`

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <Link to="/" className="header-logo">
              <span className="text-xl">⚙️</span>
              <span>项目管家</span>
            </Link>
            <nav className="header-nav">
              <Link to="/" className="nav-link">个人</Link>
              <Link to="/daily" className="nav-link active">日报</Link>
              <Link to="/projects" className="nav-link">项目</Link>
              <Link to="/chat" className="nav-link">问答</Link>
              <Link to="/dashboard" className="nav-link">看板</Link>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-menu-wrapper">
              <div 
                className="user-info"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              {/* 下拉菜单 */}
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-avatar-lg">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                    <div>
                      <div className="font-medium text-gray-900">{user?.name || '用户'}</div>
                      {user?.department && <div className="text-sm text-gray-600">{user.department}</div>}
                      {user?.position && <div className="text-xs text-gray-500">{user.position}</div>}
                    </div>
                  </div>
                  <div className="user-dropdown-divider" />
                  <button className="user-dropdown-item" onClick={handleLogout}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="content-wrapper">
        {/* 日期选择区域 */}
        <div style={{marginBottom: '16px'}}>
          <div style={{position: 'relative', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px'}}>
            <span style={{fontSize: '20px'}}>📅</span>
            <h1 
              style={{ 
                cursor: 'pointer', 
                borderBottom: '2px dashed #3b82f6', 
                paddingBottom: '2px',
                fontSize: '16px',
                fontWeight: 600,
                margin: 0
              }}
              onClick={() => setShowDatePicker(!showDatePicker)}
            >
              {formatDateDisplay(selectedDate)}
            </h1>
            <span className="tag tag-primary" style={{marginLeft: 'auto'}}>日报填报</span>
            
            {/* 日期选择下拉框 */}
            {showDatePicker && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                marginTop: '8px',
                background: 'white',
                borderRadius: '12px',
                boxShadow: '0 10px 40px rgba(0,0,0,0.15)',
                border: '1px solid #e5e7eb',
                maxHeight: '250px',
                overflowY: 'auto',
                zIndex: 100
              }}>
                {getAvailableDates().map(d => (
                  <div
                    key={d.date}
                    onClick={() => {
                      // 如果切换到新日期且已解析，询问是否保留
                      if (d.date !== selectedDate && hasParsed && dailyEntries.length > 0) {
                        // 不清空，保留解析结果（用户可能想提交到新日期）
                        // 注释掉清空逻辑，让用户自己决定
                      }
                      setSelectedDate(d.date)
                      setShowDatePicker(false)
                      // 已解析的内容不清空
                      if (!hasParsed) {
                        clearDailyEntries()
                        setParseWarnings([])
                      }
                    }}
                    style={{
                      padding: '10px 12px',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: d.date === selectedDate ? '#eff6ff' : 'white',
                      borderBottom: '1px solid #f1f5f9'
                    }}
                  >
                    <span style={{ fontWeight: d.isToday ? 600 : 400, color: '#1e293b', fontSize: '14px' }}>
                      {d.label.split(' ')[0]}
                      {d.isToday && <span style={{ color: '#3b82f6', marginLeft: '4px', fontSize: '11px' }}>今天</span>}
                    </span>
                    {d.hasReport && (
                      <span style={{ fontSize: '10px', color: '#10b981', background: '#d1fae5', padding: '2px 6px', borderRadius: '4px' }}>
                        已填报
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* 已有日报提示 */}
          {existingReport && (
            <div style={{
              marginTop: '10px',
              padding: '10px 12px',
              background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
              borderRadius: '8px',
              border: '1px solid #fbbf24',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '13px'
            }}>
              <span>💡</span>
              <span style={{ color: '#92400e' }}>
                该日期已有日报（{existingReport.total_hours.toFixed(1)}h），新提交将覆盖
              </span>
            </div>
          )}
          
          {!existingReport && selectedDate !== today && (
            <p style={{ marginTop: '8px', color: '#64748b', fontSize: '13px', marginLeft: '28px' }}>
              💡 将为该日期新建日报
            </p>
          )}
          
          {!existingReport && selectedDate === today && (
            <p style={{ marginTop: '8px', color: '#64748b', fontSize: '13px', marginLeft: '28px' }}>
              AI 智能解析，自然语言一键提交
            </p>
          )}
        </div>

        {/* 警告提示区域 */}
        {parseWarnings.length > 0 && (
          <div className="card mb-4" style={{borderColor: parseWarnings[0].type === 'error' ? '#ef4444' : '#f59e0b'}}>
            <div className="card-body" style={{padding: '16px 20px'}}>
              {parseWarnings.map((w, idx) => (
                <div key={idx} className="flex items-start gap-2" style={{color: w.type === 'error' ? '#ef4444' : '#f59e0b'}}>
                  <span>{w.type === 'error' ? '❌' : '⚠️'}</span>
                  <span>{w.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 匹配到的项目 */}
        {matchedProjects.length > 0 && (
          <div className="card mb-4">
            <div className="card-header">
              <h3 className="card-title">✅ 已匹配项目</h3>
            </div>
            <div className="card-body" style={{padding: '12px 20px'}}>
              <div className="flex flex-wrap gap-2">
                {matchedProjects.map(p => (
                  <span key={p.id} className="tag tag-success">
                    📁 {p.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 填报区域 */}
        <div className="daily-form-grid">
          {/* 左侧：输入区域 */}
          <div className="card daily-input-card">
            <div className="daily-input-header">
              <h2 className="daily-input-title">📝 工作内容</h2>
              <span className="daily-input-subtitle">自然语言描述</span>
            </div>
            <div className="daily-input-body">
              {/* 输入区域容器 */}
              <div style={{
                position: 'relative',
                borderRadius: '8px',
                overflow: 'hidden',
                flex: 1
              }}>
                {/* 解析中的遮罩层 */}
                {isParsing && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(59, 130, 246, 0.1)',
                    backdropFilter: 'blur(2px)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 10,
                    animation: 'fadeIn 0.3s ease'
                  }}>
                    <div style={{
                      padding: '20px 30px',
                      background: 'rgba(255, 255, 255, 0.95)',
                      borderRadius: '12px',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
                      animation: 'pulse 1.5s ease-in-out infinite'
                    }}>
                      <div className="flex items-center gap-3">
                        <div style={{
                          width: '32px',
                          height: '32px',
                          border: '3px solid #dbeafe',
                          borderTop: '3px solid #3b82f6',
                          borderRadius: '50%',
                          animation: 'spin 1s linear infinite'
                        }} />
                        <div>
                          <div style={{fontSize: '16px', fontWeight: '600', color: '#1e40af'}}>
                            正在智能解析...
                          </div>
                          <div style={{fontSize: '12px', color: '#64748b', marginTop: '4px'}}>
                            AI 正在识别项目和任务
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* 文本输入框 */}
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder={placeholderText}
                  className="textarea"
                  rows={10}
                  style={{
                    minHeight: '240px',
                    transition: 'all 0.3s ease',
                    opacity: isParsing ? 0.6 : 1
                  }}
                  disabled={isParsing}
                />
                
                {/* 边框动画 */}
                {isParsing && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    border: '2px solid #3b82f6',
                    borderRadius: '8px',
                    pointerEvents: 'none',
                    animation: 'borderPulse 1.5s ease-in-out infinite'
                  }} />
                )}
              </div>

              <div className="mt-6 flex justify-between items-center">
                <span className="text-sm">
                  {dailyEntries.length > 0 ? (
                    <span className="flex items-center gap-2" style={{color: 'var(--success)'}}>
                      <span className="w-2 h-2 rounded-full" style={{background: 'var(--success)'}}></span>
                      已添加 <strong>{dailyEntries.length}</strong> 条记录
                    </span>
                  ) : (
                    <span className="text-gray-400">在上方输入工作内容...</span>
                  )}
                </span>
                <button
                  onClick={handleParse}
                  disabled={!inputText.trim() || isParsing}
                  className="btn btn-primary"
                  style={{
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                >
                  {isParsing ? (
                    <span className="loading" style={{position: 'relative', zIndex: 1}}>
                      <span className="spinner"></span>
                      解析中...
                    </span>
                  ) : (
                    <>
                      <span>✨</span>
                      智能解析
                    </>
                  )}
                  
                  {/* 解析动画背景 */}
                  {isParsing && (
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
                      animation: 'shimmer 1.5s infinite'
                    }} />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* 右侧：解析结果 */}
          <div className="card daily-result-card">
            <div className="daily-result-header">
              <h2 className="daily-input-title">📋 工作记录</h2>
              <span className="flex items-center gap-2">
                <span className="text-sm text-gray-500">累计</span>
                <span className="tag tag-hours">{totalHours.toFixed(1)} 小时</span>
              </span>
            </div>
            <div className="daily-result-body">
              {dailyEntries.length === 0 ? (
                <div className="empty-state" style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                  <div>
                    <div className="empty-icon">📝</div>
                    <p className="empty-title">暂无工作记录</p>
                    <p className="empty-desc">在左侧输入工作内容，AI 将自动解析</p>
                  </div>
                </div>
              ) : (
                <div style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
                  <div className="space-y-4" style={{flex: 1, overflowY: 'auto', maxHeight: '400px'}}>
                  {dailyEntries.map((entry, index) => (
                    <div key={index} className="daily-entry-item parse-result-card" style={{animationDelay: `${index * 0.1}s`}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
                        <div style={{flex: 1, paddingLeft: '12px', minWidth: 0}}>
                          {/* 时间行 - 突出显示 */}
                          <div style={{
                            display: 'flex', 
                            flexWrap: 'wrap', 
                            alignItems: 'center', 
                            gap: '6px',
                            marginBottom: '8px'
                          }}>
                            <span className="tag tag-time" style={{whiteSpace: 'nowrap'}}>
                              🕐 {entry.start_time}-{entry.end_time}
                            </span>
                            <span className="tag tag-hours" style={{whiteSpace: 'nowrap'}}>{entry.hours}h</span>
                            {entry.location && (
                              <span className="tag tag-default" style={{whiteSpace: 'nowrap'}}>📍 {entry.location}</span>
                            )}
                          </div>
                          
                          {/* 工作内容 */}
                          <p style={{
                            color: '#1f2937',
                            fontSize: '14px',
                            lineHeight: 1.6,
                            marginBottom: '8px',
                            wordBreak: 'break-word'
                          }}>
                            {entry.content}
                          </p>
                          
                          {/* 匹配的项目 - 突出显示 */}
                          {entry.matched_project_name && (
                            <div style={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <span className="tag tag-primary" style={{whiteSpace: 'nowrap'}}>
                                🔗 {entry.matched_project_name.length > 15 
                                  ? entry.matched_project_name.substring(0, 15) + '...' 
                                  : entry.matched_project_name}
                              </span>
                              {entry.matched_task_name && (
                                <span className="tag tag-info" style={{
                                  background: '#dbeafe', 
                                  color: '#1e40af',
                                  whiteSpace: 'nowrap',
                                  maxWidth: '120px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis'
                                }}>
                                  📋 {entry.matched_task_name.length > 10 
                                    ? entry.matched_task_name.substring(0, 10) + '...' 
                                    : entry.matched_task_name}
                                </span>
                              )}
                            </div>
                          )}
                          
                          {/* 未匹配提示 */}
                          {!entry.matched_project_name && entry.project_hint && (
                            <div style={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <span className="tag tag-warning" style={{whiteSpace: 'nowrap'}}>
                                ⚠️ 未匹配
                              </span>
                              <span style={{
                                color: '#6b7280', 
                                fontSize: '12px',
                                wordBreak: 'break-word'
                              }}>{entry.project_hint}</span>
                            </div>
                          )}
                        </div>
                        
                        {/* 删除按钮 */}
                        <button
                          onClick={() => removeDailyEntry(index)}
                          style={{
                            marginLeft: '8px',
                            padding: '8px',
                            color: '#9ca3af',
                            background: 'transparent',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            flexShrink: 0
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#ef4444';
                            e.currentTarget.style.background = '#fef2f2';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#9ca3af';
                            e.currentTarget.style.background = 'transparent';
                          }}
                          title="删除此条"
                        >
                          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}

                  {/* 提交按钮 - 固定在底部 */}
                </div>
                
                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                  className="btn btn-success btn-lg w-full"
                  style={{marginTop: '16px'}}
                >
                  {isSubmitting ? (
                    <span className="loading">
                      <span className="spinner"></span>
                      提交中...
                    </span>
                  ) : (
                    <>
                      <span>✓</span>
                      确认提交日报
                    </>
                  )}
                </button>
              </div>
              )}
            </div>
          </div>
        </div>

        {/* 历史日报记录 */}
        <div className="card mt-6">
          <div className="card-header">
            <h2 className="card-title">📜 我的日报记录</h2>
            <span className="text-sm text-gray-500">最近提交</span>
          </div>
          <div className="card-body">
            {isLoadingHistory ? (
              <div className="empty-state">
                <span className="spinner"></span>
                <p className="text-gray-500 mt-2">加载中...</p>
              </div>
            ) : historyReports.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📭</div>
                <p className="empty-title">暂无历史记录</p>
                <p className="empty-desc">提交的日报将在这里显示</p>
              </div>
            ) : (
              <div className="space-y-4">
                {historyReports.map((report) => {
                  const isExpanded = expandedReports.has(report.id)
                  
                  return (
                    <div key={report.id} className="history-report-item">
                      <div 
                        style={{
                          padding: '12px',
                          borderBottom: '1px solid #e5e7eb',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '8px'
                        }}
                      >
                        {/* 第一行：日期和展开箭头 */}
                        <div 
                          onClick={() => {
                            const newExpanded = new Set(expandedReports)
                            if (isExpanded) {
                              newExpanded.delete(report.id)
                            } else {
                              newExpanded.add(report.id)
                            }
                            setExpandedReports(newExpanded)
                          }}
                          style={{ 
                            cursor: 'pointer', 
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                          }}
                        >
                          <span style={{fontSize: '18px'}}>📅</span>
                          <span style={{fontWeight: 600, color: '#1f2937', fontSize: '15px'}}>{report.report_date}</span>
                          <span style={{
                            fontSize: '11px',
                            color: '#64748b',
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s'
                          }}>▼</span>
                        </div>
                        
                        {/* 第二行：状态、工时、编辑按钮 */}
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          flexWrap: 'wrap'
                        }}>
                          <span style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: report.status === '已提交' ? '#d1fae5' : '#fef3c7',
                            color: report.status === '已提交' ? '#059669' : '#d97706'
                          }}>
                            {report.status === '已提交' ? '✓ 已提交' : report.status}
                          </span>
                          <span style={{
                            fontSize: '13px',
                            fontWeight: 600,
                            color: '#3b82f6',
                            background: '#eff6ff',
                            padding: '2px 8px',
                            borderRadius: '4px'
                          }}>
                            {report.total_hours}h
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedDate(report.report_date)
                              if (report.original_input) {
                                setInputText(report.original_input)
                              }
                              window.scrollTo({ top: 0, behavior: 'smooth' })
                            }}
                            style={{
                              padding: '4px 12px',
                              fontSize: '12px',
                              fontWeight: 500,
                              color: '#3b82f6',
                              background: '#eff6ff',
                              border: '1px solid #bfdbfe',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              marginLeft: 'auto',
                              whiteSpace: 'nowrap'
                            }}
                          >
                            编辑
                          </button>
                        </div>
                      </div>
                      
                      {isExpanded && (
                        <div className="daily-history-items">
                          {/* 原始输入 */}
                          {report.original_input && (
                            <div style={{
                              padding: '12px',
                              background: '#fef3c7',
                              borderRadius: '6px',
                              marginBottom: '12px',
                              fontSize: '13px'
                            }}>
                              <div style={{fontWeight: '600', color: '#92400e', marginBottom: '6px'}}>
                                📝 原始输入
                              </div>
                              <div style={{color: '#78350f', whiteSpace: 'pre-wrap'}}>
                                {report.original_input}
                              </div>
                            </div>
                          )}
                          
                          {/* 按项目分组的工作项 */}
                          {report.items.length === 0 ? (
                            <div style={{padding: '16px', textAlign: 'center', color: '#64748b'}}>
                              暂无详细工作项
                            </div>
                          ) : (
                            (() => {
                              // 按项目分组
                              const groupedItems = report.items.reduce((acc, item) => {
                                const projectName = item.project_name || '其他'
                                if (!acc[projectName]) {
                                  acc[projectName] = []
                                }
                                acc[projectName].push(item)
                                return acc
                              }, {} as Record<string, typeof report.items>)
                              
                              return Object.entries(groupedItems).map(([projectName, items]) => (
                                <div key={projectName} className="daily-history-group">
                                  <div className="daily-history-group-header">
                                    <span style={{fontSize: '14px'}}>📁</span>
                                    <span style={{fontSize: '14px', flex: '1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{projectName}</span>
                                    <span style={{
                                      fontSize: '11px',
                                      fontWeight: '400',
                                      color: 'rgba(255,255,255,0.8)',
                                      whiteSpace: 'nowrap'
                                    }}>
                                      {items.length}项 · {items.reduce((sum, i) => sum + i.hours_spent, 0).toFixed(1)}h
                                    </span>
                                  </div>
                                  
                                  {items.map((item, idx) => (
                                    <div key={idx} style={{
                                      padding: '10px 12px',
                                      background: '#fafafa',
                                      marginBottom: '8px',
                                      borderRadius: '6px'
                                    }}>
                                      {/* 时间和工时 - 一行显示 */}
                                      <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        marginBottom: '6px',
                                        flexWrap: 'wrap'
                                      }}>
                                        {item.start_time && item.end_time ? (
                                          <span style={{
                                            fontSize: '12px',
                                            color: '#059669',
                                            background: '#d1fae5',
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            whiteSpace: 'nowrap'
                                          }}>
                                            ⏰ {item.start_time}-{item.end_time}
                                          </span>
                                        ) : (
                                          <span style={{
                                            fontSize: '12px',
                                            color: '#94a3b8',
                                            background: '#f1f5f9',
                                            padding: '2px 6px',
                                            borderRadius: '4px'
                                          }}>
                                            ⏱️ 未记录
                                          </span>
                                        )}
                                        <span style={{
                                          fontSize: '13px',
                                          fontWeight: 600,
                                          color: '#3b82f6',
                                          marginLeft: 'auto'
                                        }}>{item.hours_spent}h</span>
                                      </div>
                                      
                                      {/* 工作内容 */}
                                      <div style={{
                                        fontSize: '13px',
                                        color: '#374151',
                                        lineHeight: 1.5,
                                        wordBreak: 'break-word'
                                      }}>{item.work_content}</div>
                                      {item.task_id && (
                                        <div style={{marginTop: '4px'}}>
                                          <span style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            padding: '2px 8px',
                                            background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                                            borderRadius: '10px',
                                            fontSize: '11px',
                                            fontWeight: '600',
                                            color: 'white',
                                            whiteSpace: 'nowrap',
                                            maxWidth: '100%',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis'
                                          }}>
                                            🎯 {item.task_name || item.task_id}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              ))
                            })()
                          )}
                          
                          {report.ai_parsed && (
                            <div style={{
                              marginTop: '12px',
                              padding: '8px 12px',
                              background: '#f0fdf4',
                              borderRadius: '6px',
                              fontSize: '12px',
                              color: '#16a34a'
                            }}>
                              ✨ AI 智能解析
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="daily" />
    </div>
  )
}
