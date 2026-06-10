import SharedHeader from '../components/SharedHeader'
import MobileNav from '../components/MobileNav'
import CalendarView from '../components/CalendarView'
import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../store'
import { dailyApi, projectApi } from '../api'
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
  shared_period?: string  // 共享时间段（多个事项共享同一时间段）
  period_total_hours?: number  // 该时间段的总工时
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
  const { dailyEntries, addDailyEntry, removeDailyEntry, clearDailyEntries,
          dailyDraft, saveDailyDraft, clearDailyDraft } = useAppStore()
  
  // 📌 所有状态变量
  const [inputText, setInputText] = useState('')
  const [isParsing, setIsParsing] = useState(false)
  const [parseMethod, setParseMethod] = useState<'cloud' | 'local' | null>(null)  // 当前解析方式
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [historyReports, setHistoryReports] = useState<HistoryReport[]>([])
  const [parseWarnings, setParseWarnings] = useState<ParseWarning[]>([])
  const [projectTasks, setProjectTasks] = useState<Record<number, Array<{task_id: string, task_name: string}>>>({})
  const [loadingTasks, setLoadingTasks] = useState<Set<number>>(new Set())
  const [taskSelectIndex, setTaskSelectIndex] = useState<number | null>(null)
  const [taskSearchText, setTaskSearchText] = useState('')
  const [matchedProjects, setMatchedProjects] = useState<Array<{id: number; name: string; leader: string}>>([])
  const [hasParsed, setHasParsed] = useState(false)
  const [showCalendar, setShowCalendar] = useState(true)
  const [viewingReport, setViewingReport] = useState<HistoryReport | null>(null)
  const [showReportModal, setShowReportModal] = useState(false)
  const [showDatePicker, setShowDatePicker] = useState(false)
  const [draftRestored, setDraftRestored] = useState(false)  // 草稿是否已恢复
  
  // 用于追踪是否已提交
  const hasSubmittedRef = useRef(false)
  
  // 日期
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const [selectedDate, setSelectedDate] = useState(today)
  
  // 📌 恢复草稿 - 使用单独的 useEffect 监听 dailyDraft 变化
  useEffect(() => {
    // 只在首次加载且草稿未恢复时执行
    if (dailyDraft && !draftRestored) {
      const draftTime = new Date(dailyDraft.updatedAt)
      const hoursSinceDraft = (Date.now() - draftTime.getTime()) / (1000 * 60 * 60)
      
      if (hoursSinceDraft < 24 && (dailyDraft.inputText.trim() || dailyDraft.entries.length > 0)) {
        console.log('[草稿恢复] 恢复内容:', dailyDraft)
        setInputText(dailyDraft.inputText)
        useAppStore.getState().setDailyEntries(dailyDraft.entries)
        setSelectedDate(dailyDraft.selectedDate)
        setParseWarnings((dailyDraft.warnings || []).map(w => ({
          type: w.type as 'warning' | 'error' | 'info',
          message: w.message
        })))
        setMatchedProjects(dailyDraft.matchedProjects || [])
        setHasParsed(dailyDraft.hasParsed)
        setDraftRestored(true)
        
        showToast(`已恢复上次未提交的日报草稿`, 'info')
      } else if (hoursSinceDraft >= 24) {
        // 草稿过期，清除
        console.log('[草稿恢复] 草稿已过期，清除')
        clearDailyDraft()
        setDraftRestored(true)
      }
    }
  }, [dailyDraft, draftRestored])
  
  // 📌 自动保存草稿（防抖）
  const saveDraftDebounced = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    // 提交后不再保存
    if (hasSubmittedRef.current) return
    
    // 只在有内容时保存
    if (!inputText.trim() && dailyEntries.length === 0) {
      return
    }
    
    if (saveDraftDebounced.current) {
      clearTimeout(saveDraftDebounced.current)
    }
    
    saveDraftDebounced.current = setTimeout(() => {
      console.log('[草稿保存] 保存内容')
      saveDailyDraft({
        inputText,
        entries: dailyEntries,
        selectedDate,
        warnings: parseWarnings,
        matchedProjects,
        hasParsed,
        updatedAt: new Date().toISOString()
      })
    }, 1000)
    
    return () => {
      if (saveDraftDebounced.current) {
        clearTimeout(saveDraftDebounced.current)
      }
    }
  }, [inputText, dailyEntries, selectedDate, hasParsed, parseWarnings, matchedProjects])
  
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
    try {
      const result = await dailyApi.getMyReports(1, 10)
      setHistoryReports(result.items || [])
    } catch (error) {
      console.error('加载历史日报失败:', error)
      setHistoryReports([])
    }
  }
  
  // 加载项目任务列表
  const loadProjectTasks = async (projectId: number) => {
    if (projectTasks[projectId] || loadingTasks.has(projectId)) return
    
    setLoadingTasks(prev => new Set(prev).add(projectId))
    try {
      const result = await projectApi.getTasks(projectId)
      setProjectTasks(prev => ({
        ...prev,
        [projectId]: result.map(t => ({
          task_id: t.task_id,
          task_name: t.task_name
        }))
      }))
    } catch (err) {
      console.error('加载任务列表失败:', err)
    } finally {
      setLoadingTasks(prev => {
        const newSet = new Set(prev)
        newSet.delete(projectId)
        return newSet
      })
    }
  }
  
  // 手动选择任务
  const handleSelectTask = (index: number, _projectId: number, taskId: string, taskName: string) => {
    const newEntries = [...dailyEntries]
    newEntries[index] = {
      ...newEntries[index],
      matched_task_id: taskId,
      matched_task_name: taskName
    }
    useAppStore.getState().setDailyEntries(newEntries)
  }
  
  // 日历选择日期（填报）- 只改日期，保留输入内容
  const handleCalendarSelectDate = (date: string) => {
    setSelectedDate(date)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  
  // 日历查看日报详情
  const handleCalendarViewReport = (report: any) => {
    if (report.has_report) {
      const historyReport: HistoryReport = {
        id: report.id,
        report_date: report.report_date,
        total_hours: report.total_hours,
        status: report.status,
        created_at: report.created_at,
        items: report.items || [],
        original_input: report.original_input,
        ai_parsed_data: report.ai_parsed_data,
        ai_parsed: report.ai_parsed
      }
      setViewingReport(historyReport)
      setShowReportModal(true)
    }
  }

  // handleParse - 云端解析函数，暂时注释
  /*
  const handleParse = async () => {
    if (!inputText.trim()) return
    
    setIsParsing(true)
    setParseMethod('cloud')
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
          { type: 'info' as const, message: '💡 提示：请描述具体的工作内容和时间，例如"xxx项目：上午完成方案编制4小时"' }
        ])
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '解析失败，请重试'
      setParseWarnings([
        { type: 'error' as const, message: `❌ ${errorMsg}` },
        { type: 'info' as const, message: '💡 请检查输入内容后重新解析，或稍后重试' }
      ])
      console.error(error)
      // 解析失败，保留输入内容
    } finally {
      setIsParsing(false)
      setParseMethod(null)
    }
  }
  */

  // 📌 本地解析（使用本地Ollama）
  const handleLocalParse = async () => {
    if (!inputText.trim()) return
    
    setIsParsing(true)
    setParseMethod('local')
    setParseWarnings([])
    setMatchedProjects([])
    
    const startTime = Date.now()  // 记录开始时间
    
    try {
      const result = await dailyApi.localParse(inputText, selectedDate)
      
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)  // 计算耗时（秒）
      
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
        
        // 标记已解析
        setHasParsed(true)
        
        // 显示成功提示（包含耗时）
        setParseWarnings([{
          type: 'info' as const,
          message: `✅ 本地解析成功！已解析 ${result.entries.length} 条工作记录${result.matched_projects?.length > 0 ? '，项目已匹配' : ''}，耗时 ${elapsed} 秒`
        }])
      } else {
        setParseWarnings([
          { type: 'error' as const, message: '⚠️ 未识别到有效的工作事项，请检查输入格式' },
          { type: 'info' as const, message: '💡 提示：请描述具体的工作内容和时间，例如"xxx项目：上午完成方案编制4小时"' }
        ])
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '本地解析失败，请重试'
      setParseWarnings([
        { type: 'error' as const, message: `❌ ${errorMsg}` },
        { type: 'info' as const, message: '💡 请检查本地Ollama服务是否正常运行' }
      ])
      console.error(error)
    } finally {
      setIsParsing(false)
      setParseMethod(null)
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
      
      // 📌 提交成功：标记已提交，清除草稿
      hasSubmittedRef.current = true
      setDraftRestored(false)
      clearDailyDraft()
      
      showToast(`${selectedDate} 日报提交成功！`, 'success')
      setInputText('')
      clearDailyEntries()
      setParseWarnings([])
      setMatchedProjects([])
      setHasParsed(false)
      loadHistoryReports()
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '提交失败，请重试'
      showToast(errorMsg, 'error')
      console.error(error)
    } finally {
      setIsSubmitting(false)
    }
  }


  const totalHours = dailyEntries.reduce((sum, e) => {
    // 如果 hours=0 且有共享时间段，使用 period_total_hours
    // 但同一时间段只计算一次（通过 shared_period 去重）
    if (e.hours === 0 && e.shared_period && e.period_total_hours) {
      // 检查是否已经计算过这个时间段
      const firstWithSamePeriod = dailyEntries.findIndex(
        entry => entry.shared_period === e.shared_period
      )
      // 只计算第一个出现的时间段
      if (firstWithSamePeriod === dailyEntries.indexOf(e)) {
        return sum + e.period_total_hours
      }
      return sum
    }
    return sum + (e.hours || 0)
  }, 0)
  
  // 获取每个事项的显示工时
  const getDisplayHours = (entry: typeof dailyEntries[0]) => {
    // 如果 hours=0 且有共享时间段，显示总工时
    if (entry.hours === 0 && entry.shared_period && entry.period_total_hours) {
      return entry.period_total_hours
    }
    return entry.hours || 0
  }

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
      <SharedHeader />

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
                      // 只改日期，保留输入内容（草稿会自动保存）
                      setSelectedDate(d.date)
                      setShowDatePicker(false)
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
              {/* 复制上次日报按钮 */}
              {historyReports.length > 0 && (
                <div style={{
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <button
                    onClick={() => {
                      // 按日期排序，取最新的日报
                      const latestReport = historyReports
                        .sort((a, b) => new Date(b.report_date).getTime() - new Date(a.report_date).getTime())[0]
                      
                      if (latestReport) {
                        // 复制原始输入到输入框
                        if (latestReport.original_input) {
                          setInputText(latestReport.original_input)
                          showToast(`已复制 ${latestReport.report_date} 的日报内容`, 'success')
                        } else {
                          // 如果没有原始输入，从工作项重构文本
                          const reconstructed = latestReport.items
                            .map(item => {
                              let text = item.work_content
                              if (item.start_time && item.end_time) {
                                text = `${item.start_time}-${item.end_time} ${text}`
                              }
                              if (item.project_name) {
                                text += ` (${item.project_name})`
                              }
                              return text
                            })
                            .join('\n')
                          
                          setInputText(reconstructed)
                          showToast(`已从 ${latestReport.report_date} 的日报重构内容`, 'success')
                        }
                        
                        // 清空之前的解析结果
                        clearDailyEntries()
                        setParseWarnings([])
                        setMatchedProjects([])
                        setHasParsed(false)
                      }
                    }}
                    style={{
                      padding: '8px 16px',
                      fontSize: '13px',
                      fontWeight: 500,
                      color: '#3b82f6',
                      background: '#eff6ff',
                      border: '1px solid #bfdbfe',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.2s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#dbeafe'
                      e.currentTarget.style.borderColor = '#3b82f6'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#eff6ff'
                      e.currentTarget.style.borderColor = '#bfdbfe'
                    }}
                  >
                    <span>📋</span>
                    <span>复制上次日报</span>
                  </button>
                  
                  {/* 显示上次日报日期 */}
                  {historyReports.length > 0 && (
                    <span style={{
                      fontSize: '12px',
                      color: '#6b7280'
                    }}>
                      最近: {historyReports.sort((a, b) => new Date(b.report_date).getTime() - new Date(a.report_date).getTime())[0]?.report_date}
                    </span>
                  )}
                </div>
              )}
              
              {/* 草稿自动保存提示 */}
              {(inputText.trim() || dailyEntries.length > 0) && (
                <div style={{
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  color: '#10b981'
                }}>
                  <span>💾</span>
                  <span>内容已自动保存为草稿，切换页面后可恢复</span>
                </div>
              )}
              
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
                            AI 正在识别项目和任务（预计 10-60 秒）
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
                  {/* 解析按钮组 */}
                  <div style={{ display: 'flex', gap: '8px' }}>
                  {/* 云端解析（DeepSeek） - 暂时注释，观察本地解析效果 */}
                  {/*
                  <button
                    onClick={handleParse}
                    disabled={!inputText.trim() || isParsing}
                    className="btn btn-primary"
                    style={{
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                  >
                    {isParsing && parseMethod === 'cloud' ? (
                      <span className="loading" style={{position: 'relative', zIndex: 1}}>
                        <span className="spinner"></span>
                        云端解析...
                      </span>
                    ) : (
                      <>
                        <span>☁️</span>
                        云端解析
                      </>
                    )}
                    
                    {isParsing && parseMethod === 'cloud' && (
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
                  */}
                  
                  {/* 本地解析（Ollama） */}
                  <button
                    onClick={handleLocalParse}
                    disabled={!inputText.trim() || isParsing}
                    className="btn"
                    title="🚀 调用本地部署 qwen 模型，速度快、隐私安全！让我们一起体验AI的力量～"
                    style={{
                      position: 'relative',
                      overflow: 'hidden',
                      background: isParsing && parseMethod === 'local' ? '#10b981' : '#059669',
                      color: 'white',
                      border: 'none'
                    }}
                  >
                    {isParsing && parseMethod === 'local' ? (
                      <span className="loading" style={{position: 'relative', zIndex: 1}}>
                        <span className="spinner"></span>
                        本地解析...
                      </span>
                    ) : (
                      <>
                        <span>🏠</span>
                        本地解析
                      </>
                    )}
                    
                    {isParsing && parseMethod === 'local' && (
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
                            {/* 显示工时（共享时段显示总工时） */}
                            <span className="tag tag-hours" style={{whiteSpace: 'nowrap'}}>
                              {getDisplayHours(entry).toFixed(1)}h
                              {entry.hours === 0 && entry.shared_period && (
                                <span style={{marginLeft: '4px', fontSize: '10px', opacity: 0.8}}>共享</span>
                              )}
                            </span>
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
                              {/* 已匹配任务 */}
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
                              {/* 未匹配任务时显示选择按钮 */}
                              {!entry.matched_task_name && entry.matched_project_id && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setTaskSelectIndex(index)
                                    setTaskSearchText('')
                                    loadProjectTasks(entry.matched_project_id!)
                                  }}
                                  style={{
                                    fontSize: '11px',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    border: '1px solid #bfdbfe',
                                    background: '#eff6ff',
                                    color: '#3b82f6',
                                    cursor: 'pointer',
                                    whiteSpace: 'nowrap'
                                  }}
                                >
                                  + 选择任务
                                </button>
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

        {/* 日历视图 - 历史日报快速定位 */}
        <div className="card mt-6">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 className="card-title">📅 历史日报日历</h2>
            <button
              onClick={() => setShowCalendar(!showCalendar)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 500,
                color: showCalendar ? '#64748b' : '#3b82f6',
                background: showCalendar ? '#f1f5f9' : '#eff6ff',
                border: '1px solid ' + (showCalendar ? '#e5e7eb' : '#bfdbfe'),
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              {showCalendar ? '收起' : '展开'}
            </button>
          </div>
          {showCalendar && (
            <div className="card-body" style={{ padding: '16px' }}>
              <CalendarView 
                onSelectDate={handleCalendarSelectDate}
                onViewReport={handleCalendarViewReport}
              />
            </div>
          )}
        </div>

      </main>

      {/* 日报详情弹窗 */}
      {showReportModal && viewingReport && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px'
          }}
          onClick={() => setShowReportModal(false)}
        >
          <div 
            style={{
              background: 'white',
              borderRadius: '16px',
              maxWidth: '500px',
              width: '100%',
              maxHeight: '80vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗头部 */}
            <div style={{
              padding: '16px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
              color: 'white'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: '600' }}>
                    📅 {viewingReport.report_date}
                  </div>
                  <div style={{ fontSize: '13px', opacity: 0.8, marginTop: '4px' }}>
                    {viewingReport.status} · {viewingReport.total_hours.toFixed(1)} 小时
                  </div>
                </div>
                <button
                  onClick={() => setShowReportModal(false)}
                  style={{
                    background: 'rgba(255,255,255,0.2)',
                    border: 'none',
                    color: 'white',
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '18px'
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
            
            {/* 弹窗内容 */}
            <div style={{ 
              padding: '16px', 
              overflowY: 'auto',
              flex: 1 
            }}>
              {/* 原始输入 */}
              {viewingReport.original_input && (
                <div style={{
                  padding: '12px',
                  background: '#fef3c7',
                  borderRadius: '8px',
                  marginBottom: '12px',
                  fontSize: '13px'
                }}>
                  <div style={{ fontWeight: '600', color: '#92400e', marginBottom: '6px' }}>
                    📝 原始输入
                  </div>
                  <div style={{ color: '#78350f', whiteSpace: 'pre-wrap' }}>
                    {viewingReport.original_input}
                  </div>
                </div>
              )}
              
              {/* 按项目分组的工作项 */}
              {viewingReport.items && viewingReport.items.length > 0 ? (
                (() => {
                  const groupedItems = viewingReport.items.reduce((acc, item) => {
                    const projectName = item.project_name || '其他'
                    if (!acc[projectName]) acc[projectName] = []
                    acc[projectName].push(item)
                    return acc
                  }, {} as Record<string, typeof viewingReport.items>)
                  
                  return Object.entries(groupedItems).map(([projectName, items]) => (
                    <div key={projectName} style={{ marginBottom: '12px' }}>
                      <div style={{
                        padding: '8px 12px',
                        background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                        borderRadius: '8px 8px 0 0',
                        color: 'white',
                        fontSize: '13px',
                        fontWeight: '500'
                      }}>
                        📁 {projectName}
                        <span style={{ marginLeft: '8px', opacity: 0.8 }}>
                          ({items.length}项 · {items.reduce((s, i) => s + i.hours_spent, 0).toFixed(1)}h)
                        </span>
                      </div>
                      <div style={{ background: '#f8fafc', borderRadius: '0 0 8px 8px', padding: '8px' }}>
                        {items.map((item, idx) => (
                          <div key={idx} style={{
                            padding: '8px',
                            background: 'white',
                            marginBottom: '6px',
                            borderRadius: '6px',
                            border: '1px solid #e5e7eb'
                          }}>
                            <div style={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: '6px',
                              marginBottom: '4px',
                              flexWrap: 'wrap'
                            }}>
                              {item.start_time && item.end_time && (
                                <span style={{
                                  fontSize: '11px',
                                  color: '#059669',
                                  background: '#d1fae5',
                                  padding: '2px 6px',
                                  borderRadius: '4px'
                                }}>
                                  ⏰ {item.start_time}-{item.end_time}
                                </span>
                              )}
                              <span style={{
                                fontSize: '13px',
                                fontWeight: '600',
                                color: '#3b82f6',
                                marginLeft: 'auto'
                              }}>{item.hours_spent}h</span>
                            </div>
                            <div style={{ fontSize: '13px', color: '#374151' }}>
                              {item.work_content}
                            </div>
                            {item.task_id && (
                              <div style={{ marginTop: '4px' }}>
                                <span style={{
                                  display: 'inline-block',
                                  padding: '2px 8px',
                                  background: '#fef3c7',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  color: '#92400e'
                                }}>
                                  🎯 {item.task_name || item.task_id}
                                </span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                })()
              ) : (
                <div style={{ textAlign: 'center', color: '#64748b', padding: '20px' }}>
                  暂无详细工作项
                </div>
              )}
              
              {viewingReport.ai_parsed && (
                <div style={{
                  marginTop: '12px',
                  textAlign: 'center',
                  padding: '8px',
                  background: '#f0fdf4',
                  borderRadius: '8px',
                  fontSize: '12px',
                  color: '#16a34a'
                }}>
                  ✨ AI 智能解析
                </div>
              )}
            </div>
            
            {/* 弹窗底部 */}
            <div style={{
              padding: '12px 16px',
              borderTop: '1px solid #e5e7eb',
              display: 'flex',
              gap: '8px'
            }}>
              <button
                onClick={() => {
                  setShowReportModal(false)
                  handleCalendarSelectDate(viewingReport.report_date)
                  if (viewingReport.original_input) {
                    setInputText(viewingReport.original_input)
                  }
                }}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#eff6ff',
                  border: '1px solid #bfdbfe',
                  borderRadius: '8px',
                  color: '#3b82f6',
                  fontWeight: '500',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                ✏️ 编辑此日报
              </button>
              <button
                onClick={() => setShowReportModal(false)}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#f1f5f9',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  color: '#64748b',
                  fontWeight: '500',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 任务选择弹窗 */}
      {taskSelectIndex !== null && dailyEntries[taskSelectIndex] && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px'
          }}
          onClick={() => setTaskSelectIndex(null)}
        >
          <div 
            style={{
              background: 'white',
              borderRadius: '16px',
              maxWidth: '400px',
              width: '100%',
              maxHeight: '70vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗头部 */}
            <div style={{
              padding: '16px',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ fontSize: '16px', fontWeight: '600', color: '#1f2937' }}>
                  选择任务
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                  {dailyEntries[taskSelectIndex].matched_project_name}
                </div>
              </div>
              <button
                onClick={() => setTaskSelectIndex(null)}
                style={{
                  background: '#f3f4f6',
                  border: 'none',
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '18px',
                  color: '#6b7280'
                }}
              >
                ✕
              </button>
            </div>
            
            {/* 搜索框 */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>
              <input
                type="text"
                placeholder="搜索任务名称..."
                value={taskSearchText}
                onChange={(e) => setTaskSearchText(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: '14px',
                  outline: 'none'
                }}
                autoFocus
              />
            </div>
            
            {/* 任务列表 */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
              {loadingTasks.has(dailyEntries[taskSelectIndex].matched_project_id!) ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#6b7280' }}>
                  加载中...
                </div>
              ) : (
                (() => {
                  const projectId = dailyEntries[taskSelectIndex].matched_project_id!
                  const tasks = projectTasks[projectId] || []
                  const filteredTasks = tasks.filter(t => 
                    t.task_name.toLowerCase().includes(taskSearchText.toLowerCase())
                  )
                  
                  if (filteredTasks.length === 0) {
                    return (
                      <div style={{ textAlign: 'center', padding: '20px', color: '#9ca3af' }}>
                        {taskSearchText ? '未找到匹配的任务' : '暂无任务'}
                      </div>
                    )
                  }
                  
                  return filteredTasks.map(t => (
                    <div
                      key={t.task_id}
                      onClick={() => {
                        handleSelectTask(taskSelectIndex, projectId, t.task_id, t.task_name)
                        setTaskSelectIndex(null)
                        setTaskSearchText('')
                      }}
                      style={{
                        padding: '12px 16px',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        marginBottom: '4px',
                        transition: 'background 0.15s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f3f4f6'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      <div style={{ fontSize: '14px', color: '#1f2937' }}>
                        {t.task_name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                        {t.task_id}
                      </div>
                    </div>
                  ))
                })()
              )}
            </div>
          </div>
        </div>
      )}

      {/* 移动端底部导航 */}
      <MobileNav active="daily" />
    </div>
  )
}
