import { Link } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'

export default function WeeklyReportPage() {
  const { user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [reports, setReports] = useState<any[]>([])
  const [selectedReport, setSelectedReport] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    loadReports()
  }, [page])

  const loadReports = async () => {
    setIsLoading(true)
    try {
      const token = useAppStore.getState().token
      const response = await fetch(`/api/agent/weekly-reports?page=${page}&size=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const result = await response.json()
      if (result.success) {
        setReports(result.data.items)
        setTotal(result.data.total)
      }
    } catch (error) {
      console.error('加载周报列表失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const generateReport = async () => {
    setIsGenerating(true)
    try {
      const token = useAppStore.getState().token
      const response = await fetch('/api/agent/weekly-reports/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({})
      })
      const result = await response.json()
      
      if (result.success) {
        alert(`✅ 成功生成 ${result.data.reports.length} 份周报！`)
        loadReports()
      } else {
        alert(result.message || '生成失败')
      }
    } catch (error: any) {
      alert('生成失败: ' + error.message)
    } finally {
      setIsGenerating(false)
    }
  }

  const viewReportDetail = async (reportId: number) => {
    try {
      const token = useAppStore.getState().token
      const response = await fetch(`/api/agent/weekly-reports/${reportId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const result = await response.json()
      if (result.success) {
        setSelectedReport(result.data)
      }
    } catch (error) {
      console.error('加载周报详情失败:', error)
    }
  }

  const handleCopy = async () => {
    if (selectedReport?.ai_analysis) {
      const analysis = selectedReport.ai_analysis
      const text = `# ${selectedReport.project_name} 周报
时间：${selectedReport.week_start} ~ ${selectedReport.week_end}

## 📋 本周概述
${analysis.summary || ''}

## 📊 项目进展
${(analysis.project_progress || []).map((p: any) => `- **${p.name}**：${p.progress}（${p.hours}h）`).join('\n')}

## 🎯 下周重点
${(analysis.next_week_focus || []).map((f: string) => `- ${f}`).join('\n')}

## 💡 工作亮点
${(analysis.highlights || []).map((h: string) => `- ${h}`).join('\n')}

---
*总工时：${selectedReport.total_hours}h | 任务数：${selectedReport.task_count}*`
      
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

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
              <Link to="/daily" className="nav-link">日报</Link>
              <Link to="/projects" className="nav-link">项目</Link>
              <Link to="/chat" className="nav-link">问答</Link>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-menu-wrapper">
              <div className="user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
                <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
              </div>
              {showUserMenu && (
                <div className="user-dropdown">
                  <button className="user-dropdown-item" onClick={handleLogout}>退出登录</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="content-wrapper">
        {selectedReport ? (
          // 周报详情视图
          <div>
            {/* 移动端适配：返回按钮单独一行 */}
            <div className="mb-4">
              <button onClick={() => setSelectedReport(null)} className="btn" style={{ background: '#f1f5f9' }}>
                ← 返回列表
              </button>
            </div>
            
            {/* 标题行 */}
            <div className="flex items-start justify-between mb-6 gap-4 flex-col sm:flex-row">
              <div className="flex-1">
                <h1 className="text-xl sm:text-2xl font-bold text-gray-900">📊 {selectedReport.project_name}</h1>
                <p className="text-gray-500 mt-1 text-sm sm:text-base">
                  {selectedReport.week_start} ~ {selectedReport.week_end}
                </p>
              </div>
              <button onClick={handleCopy} className="btn btn-primary shrink-0">
                {copied ? '✓ 已复制' : '📋 复制周报'}
              </button>
            </div>

            {/* 统计卡片 */}
            <div className="grid-3 mb-6">
              <div className="stat-card">
                <div className="stat-content">
                  <div className="stat-value">{selectedReport.total_hours}<span className="stat-unit">h</span></div>
                  <div className="stat-label">累计工时</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-content">
                  <div className="stat-value">{selectedReport.task_count}</div>
                  <div className="stat-label">任务数量</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-content">
                  <div className="stat-value">{selectedReport.daily_items?.length || 0}</div>
                  <div className="stat-label">日报条目</div>
                </div>
              </div>
            </div>

            {/* AI 分析结果 */}
            {selectedReport.ai_analysis && (
              <>
                <div className="card mb-6">
                  <div className="card-header">
                    <h2 className="card-title">📋 本周工作概述</h2>
                  </div>
                  <div className="card-body">
                    <p style={{ lineHeight: 1.8, color: '#374151' }}>
                      {selectedReport.ai_analysis.summary}
                    </p>
                  </div>
                </div>

                {/* 项目进展 */}
                {selectedReport.ai_analysis.project_progress?.length > 0 && (
                  <div className="card mb-6">
                    <div className="card-header">
                      <h2 className="card-title">📊 项目进展</h2>
                    </div>
                    <div className="card-body">
                      {selectedReport.ai_analysis.project_progress.map((p: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-start py-3 border-b border-gray-100 last:border-0">
                          <div style={{ flex: 1 }}>
                            <div className="font-medium text-gray-900">{p.name}</div>
                            <div className="text-sm text-gray-600 mt-1">{p.progress}</div>
                          </div>
                          <span className="font-medium text-blue-600 ml-4">{p.hours}h</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 下周重点 */}
                {selectedReport.ai_analysis.next_week_focus?.length > 0 && (
                  <div className="card mb-6">
                    <div className="card-header">
                      <h2 className="card-title">🎯 下周重点关注</h2>
                    </div>
                    <div className="card-body">
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {selectedReport.ai_analysis.next_week_focus.map((f: string, idx: number) => (
                          <li key={idx} style={{ padding: '8px 0', color: '#374151' }}>{f}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* 工作亮点 */}
                {selectedReport.ai_analysis.highlights?.length > 0 && (
                  <div className="card mb-6">
                    <div className="card-header">
                      <h2 className="card-title">💡 工作亮点</h2>
                    </div>
                    <div className="card-body">
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {selectedReport.ai_analysis.highlights.map((h: string, idx: number) => (
                          <li key={idx} style={{ padding: '8px 0', color: '#059669' }}>{h}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* 日报明细 */}
            {selectedReport.daily_items?.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">📝 日报明细</h2>
                </div>
                <div className="card-body" style={{ maxHeight: 400, overflow: 'auto' }}>
                  {selectedReport.daily_items.map((item: any, idx: number) => (
                    <div key={idx} className="py-2 border-b border-gray-100 last:border-0">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-sm text-gray-500">{item.date} · {item.employee}</span>
                        <span className="text-sm font-medium text-blue-600">{item.hours}h</span>
                      </div>
                      <div className="text-gray-700 text-sm">{item.content}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          // 周报列表视图
          <div>
            <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">📊 智能周报</h1>
                <p className="text-gray-500 mt-1">基于日报数据自动生成项目周报</p>
              </div>
              <button 
                onClick={generateReport} 
                className="btn btn-primary"
                disabled={isGenerating}
              >
                {isGenerating ? '⏳ 生成中...' : '✨ 生成上周周报'}
              </button>
            </div>

            {isLoading ? (
              <div className="empty-state" style={{ padding: '80px' }}>
                <span className="spinner" style={{ width: '40px', height: '40px' }}></span>
                <p className="text-gray-500 mt-4">加载中...</p>
              </div>
            ) : reports.length > 0 ? (
              <div className="grid-2">
                {reports.map((report) => (
                  <div 
                    key={report.id} 
                    className="card" 
                    style={{ cursor: 'pointer' }}
                    onClick={() => viewReportDetail(report.id)}
                  >
                    <div className="card-body">
                      <div className="flex justify-between items-start mb-3">
                        <h3 className="font-medium text-gray-900">{report.project_name}</h3>
                        <span className="text-sm text-gray-500">
                          {report.week_start?.slice(5)} ~ {report.week_end?.slice(5)}
                        </span>
                      </div>
                      <div className="flex gap-4 text-sm text-gray-600">
                        <span>⏱️ {report.total_hours}h</span>
                        <span>📋 {report.task_count}项</span>
                      </div>
                      {report.summary && (
                        <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                          {report.summary}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">📭</div>
                <p className="empty-title">暂无周报</p>
                <p className="empty-desc">点击上方按钮生成上周周报</p>
              </div>
            )}

            {/* 分页 */}
            {total > 10 && (
              <div className="flex justify-center gap-2 mt-6">
                <button 
                  className="btn" 
                  style={{ background: '#f1f5f9' }}
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  上一页
                </button>
                <span className="px-4 py-2 text-gray-600">
                  第 {page} 页 / 共 {Math.ceil(total / 10)} 页
                </span>
                <button 
                  className="btn" 
                  style={{ background: '#f1f5f9' }}
                  disabled={page * 10 >= total}
                  onClick={() => setPage(page + 1)}
                >
                  下一页
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* 移动端底部导航 */}
      <nav className="mobile-nav">
        <Link to="/" className="mobile-nav-item">
          <span className="mobile-nav-icon">🏠</span>
          <span>首页</span>
        </Link>
        <Link to="/daily" className="mobile-nav-item">
          <span className="mobile-nav-icon">📝</span>
          <span>日报</span>
        </Link>
        <Link to="/projects" className="mobile-nav-item">
          <span className="mobile-nav-icon">📊</span>
          <span>项目</span>
        </Link>
      </nav>

      <style>{`
        .line-clamp-2 {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
      `}</style>
    </div>
  )
}
