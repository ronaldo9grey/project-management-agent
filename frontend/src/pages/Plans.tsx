import { Link, useSearchParams } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../store'
import { plansApi, projectsApi } from '../api'
import * as XLSX from 'xlsx'
// import * as XLSX from 'xlsx' // Excel预览功能待完善

interface Project {
  id: number
  name: string
  leader: string
  status: string
}

interface PlanVersion {
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
}

interface CompareResult {
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

export default function PlansPage() {
  const { user, logout } = useAppStore()
  const [searchParams] = useSearchParams()
  const projectIdFromUrl = searchParams.get('project_id')
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [versions, setVersions] = useState<PlanVersion[]>([])
  const [isLoadingProjects, setIsLoadingProjects] = useState(true)
  const [isLoadingVersions, setIsLoadingVersions] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showCompareModal, setShowCompareModal] = useState(false)
  
  // 上传相关
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [versionName, setVersionName] = useState('')
  const [versionDesc, setVersionDesc] = useState('')
  const [uploadResult, setUploadResult] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // 对比相关
  const [compareVersions, setCompareVersions] = useState<[number | null, number | null]>([null, null])
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [isComparing, setIsComparing] = useState(false)
  const [noVersionToCompare, setNoVersionToCompare] = useState(false)

  useEffect(() => {
    loadProjects()
  }, [])

  // 当打开对比弹窗时，自动选择最新两个版本并触发对比
  useEffect(() => {
    if (showCompareModal && versions.length >= 2) {
      // 版本按 id 降序排列（最新在前），取前两个
      const sortedVersions = [...versions].sort((a, b) => b.id - a.id)
      const newVersionId = sortedVersions[0].id
      const oldVersionId = sortedVersions[1].id
      setCompareVersions([oldVersionId, newVersionId])
      setNoVersionToCompare(false)
    } else if (showCompareModal && versions.length < 2) {
      setNoVersionToCompare(true)
      setCompareVersions([null, null])
      setCompareResult(null)
    }
  }, [showCompareModal, versions])

  // 自动触发对比
  useEffect(() => {
    if (compareVersions[0] && compareVersions[1] && !compareResult && !isComparing && showCompareModal) {
      const doCompare = async () => {
        setIsComparing(true)
        try {
          const result = await plansApi.compareVersions(compareVersions[0]!, compareVersions[1]!)
          setCompareResult(result)
        } catch (error: any) {
          console.error('对比失败:', error)
        } finally {
          setIsComparing(false)
        }
      }
      doCompare()
    }
  }, [compareVersions, showCompareModal])

  useEffect(() => {
    if (selectedProject) {
      loadVersions(selectedProject.id)
    }
  }, [selectedProject])

  const loadProjects = async () => {
    setIsLoadingProjects(true)
    try {
      const result = await projectsApi.getList()
      setProjects(result)
      if (result.length > 0) {
        // 如果 URL 有 project_id 参数，优先选中该项目
        if (projectIdFromUrl) {
          const targetProject = result.find((p: Project) => String(p.id) === projectIdFromUrl)
          if (targetProject) {
            setSelectedProject(targetProject)
          } else {
            setSelectedProject(result[0])
          }
        } else {
          setSelectedProject(result[0])
        }
      }
    } catch (error) {
      console.error('加载项目列表失败:', error)
    } finally {
      setIsLoadingProjects(false)
    }
  }

  const loadVersions = async (projectId: number) => {
    setIsLoadingVersions(true)
    try {
      const result = await plansApi.getVersions(projectId)
      setVersions(result)
    } catch (error) {
      console.error('加载版本列表失败:', error)
      setVersions([])
    } finally {
      setIsLoadingVersions(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setUploadFile(file)
    }
  }

  const handleUpload = async () => {
    if (!uploadFile || !selectedProject) return
    
    setIsUploading(true)
    setUploadResult(null)
    
    try {
      const result = await plansApi.uploadPlan(selectedProject.id, uploadFile, versionName, versionDesc)
      setUploadResult(result)
      // 刷新版本列表
      await loadVersions(selectedProject.id)
      // 清空表单
      setUploadFile(null)
      setVersionName('')
      setVersionDesc('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '上传失败'
      setUploadResult({ success: false, message: errorMsg })
    } finally {
      setIsUploading(false)
    }
  }

  // Excel预览功能
  const [previewVersion, setPreviewVersion] = useState<any>(null)
  const [previewHtml, setPreviewHtml] = useState<string>('')
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)

  const handlePreviewExcel = async (version: any) => {
    if (!version.file_name) {
      alert('该版本没有关联的Excel文件')
      return
    }
    
    setPreviewVersion(version)
    setIsLoadingPreview(true)
    setPreviewHtml('')
    
    try {
      const res = await fetch(`/api/agent/plans/file/${version.id}`, {
        headers: { 'Authorization': `Bearer ${useAppStore.getState().token}` }
      })
      if (!res.ok) throw new Error('文件不存在')
      
      const blob = await res.blob()
      const data = await blob.arrayBuffer()
      const wb = XLSX.read(data, { type: 'array' })
      const sheet = wb.Sheets[wb.SheetNames[0]]
      const html = XLSX.utils.sheet_to_html(sheet)
      setPreviewHtml(html)
    } catch (e: any) {
      alert(`预览失败: ${e.message}`)
      setPreviewVersion(null)
    } finally {
      setIsLoadingPreview(false)
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  // Excel预览功能（待完善）
  // const handlePreviewExcel = async (version: PlanVersion) => {
  //   // 预览功能开发中
  //   alert('预览功能开发中，敬请期待！')
  // }

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
              <Link to="/dashboard" className="nav-link">看板</Link>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-menu-wrapper">
              <div className="user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
                <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
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
        {/* 返回按钮 */}
        {projectIdFromUrl && (
          <div className="mb-4">
            <Link 
              to={`/projects/${projectIdFromUrl}`} 
              className="back-link"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              返回项目详情
            </Link>
          </div>
        )}
        
        {/* 标题 */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">📁 项目计划管理</h1>
          <p className="text-gray-500 mt-1">上传Excel计划，智能解析任务，版本对比分析</p>
        </div>

        {/* 项目选择 */}
        <div className="card mb-6">
          <div className="card-header">
            <h2 className="card-title">选择项目</h2>
          </div>
          <div className="card-body">
            {isLoadingProjects ? (
              <div className="empty-state" style={{padding: '20px'}}>
                <span className="spinner"></span>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {projects.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProject(p)}
                    className={`tag cursor-pointer transition-all ${selectedProject?.id === p.id ? 'tag-primary' : 'tag-default'}`}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {selectedProject && (
          <>
            {/* 操作按钮 */}
            <div className="flex gap-3 mb-6">
              <button
                onClick={() => setShowUploadModal(true)}
                className="btn btn-primary"
              >
                <span>📤</span>
                上传新计划
              </button>
              {versions.length >= 2 && (
                <button
                  onClick={() => setShowCompareModal(true)}
                  className="btn btn-secondary"
                >
                  <span>🔍</span>
                  版本对比
                </button>
              )}
            </div>

            {/* 版本列表 */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">版本历史</h2>
                <span className="text-sm text-gray-500">{versions.length} 个版本</span>
              </div>
              <div className="card-body">
                {isLoadingVersions ? (
                  <div className="empty-state">
                    <span className="spinner"></span>
                  </div>
                ) : versions.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <p className="empty-title">暂无计划版本</p>
                    <p className="empty-desc">点击"上传新计划"导入Excel文件</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {versions.map(v => (
                      <div key={v.id} className="list-item">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">📋</span>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-medium text-gray-900">{v.version_name}</span>
                                {v.is_current && (
                                  <span className="tag tag-success">当前版本</span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-1 text-sm text-gray-500 flex-wrap">
                                <span>版本号: {v.version_number}</span>
                                <span className="hidden sm:inline">•</span>
                                <span>{v.task_count} 个任务</span>
                                {v.file_name && (
                                  <>
                                    <span className="hidden sm:inline">•</span>
                                    <span 
                                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 cursor-pointer transition-colors"
                                      onClick={() => handlePreviewExcel(v)}
                                      title="点击预览Excel文件"
                                    >
                                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                      </svg>
                                      <span className="underline decoration-dotted hover:decoration-solid">{v.file_name}</span>
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="text-right text-sm text-gray-500">
                            <div>{v.upload_time ? new Date(v.upload_time).toLocaleDateString('zh-CN') : '-'}</div>
                            <div>{v.upload_by || ''}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>

      {/* 上传弹窗 */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">📤 上传计划</h3>
              <button className="modal-close" onClick={() => setShowUploadModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {selectedProject && (
                <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                  <span className="text-blue-700">📁 {selectedProject.name}</span>
                </div>
              )}
              
              {/* 文件选择 */}
              <div className="form-group">
                <label className="form-label">Excel文件</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleFileSelect}
                  className="input"
                />
                <p className="form-hint">
                  支持格式: .xlsx, .xls<br/>
                  必须包含列: 任务名称<br/>
                  可选列: 负责人、开始日期、结束日期、工时、状态、备注
                </p>
              </div>

              {/* 版本名称 */}
              <div className="form-group">
                <label className="form-label">版本名称（可选）</label>
                <input
                  type="text"
                  value={versionName}
                  onChange={e => setVersionName(e.target.value)}
                  placeholder="如: V2.0 - 需求变更版"
                  className="input"
                />
              </div>

              {/* 版本说明 */}
              <div className="form-group">
                <label className="form-label">版本说明（可选）</label>
                <textarea
                  value={versionDesc}
                  onChange={e => setVersionDesc(e.target.value)}
                  placeholder="描述本次更新的内容..."
                  className="textarea"
                  rows={3}
                />
              </div>

              {/* 上传结果 */}
              {uploadResult && (
                <div className={`mt-4 p-4 rounded-lg ${uploadResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
                  <div className={`font-medium ${uploadResult.success ? 'text-green-700' : 'text-red-700'}`}>
                    {uploadResult.success ? '✅ ' : '❌ '}{uploadResult.message}
                  </div>
                  {uploadResult.success && uploadResult.task_count > 0 && (
                    <div className="mt-2 text-sm text-green-600">
                      版本: {uploadResult.version_name} ({uploadResult.version_number})
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button
                onClick={() => setShowUploadModal(false)}
                className="btn btn-secondary"
              >
                关闭
              </button>
              <button
                onClick={handleUpload}
                disabled={!uploadFile || isUploading}
                className="btn btn-primary"
              >
                {isUploading ? (
                  <span className="loading">
                    <span className="spinner"></span>
                    上传中...
                  </span>
                ) : (
                  <>📤 上传并解析</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 对比弹窗 */}
      {showCompareModal && (
        <div className="modal-overlay" onClick={() => setShowCompareModal(false)}>
          <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">🔍 版本对比</h3>
              <button className="modal-close" onClick={() => setShowCompareModal(false)}>×</button>
            </div>
            <div className="modal-body">
              {/* 无足够版本提示 */}
              {noVersionToCompare ? (
                <div className="text-center py-8">
                  <div className="text-gray-400 text-5xl mb-4">📋</div>
                  <p className="text-gray-500">当前项目版本数不足，无法进行版本对比</p>
                  <p className="text-gray-400 text-sm mt-2">至少需要上传2个版本的计划</p>
                </div>
              ) : (
                <>
                  {/* 版本选择 */}
                  <div className="grid-2 mb-4">
                    <div className="form-group">
                      <label className="form-label">旧版本</label>
                      <select
                        value={compareVersions[0] || ''}
                        onChange={e => {
                          setCompareVersions([Number(e.target.value), compareVersions[1]])
                          setCompareResult(null) // 切换版本时清空结果
                        }}
                        className="input"
                      >
                        <option value="">选择版本...</option>
                        {versions.map(v => (
                          <option key={v.id} value={v.id}>{v.version_name} ({v.version_number})</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">新版本</label>
                      <select
                        value={compareVersions[1] || ''}
                        onChange={e => {
                          setCompareVersions([compareVersions[0], Number(e.target.value)])
                          setCompareResult(null) // 切换版本时清空结果
                        }}
                        className="input"
                      >
                        <option value="">选择版本...</option>
                        {versions.map(v => (
                          <option key={v.id} value={v.id}>{v.version_name} ({v.version_number})</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* 加载中提示 */}
                  {isComparing && (
                    <div className="text-center py-8">
                      <span className="loading">
                        <span className="spinner"></span>
                        正在对比版本...
                      </span>
                    </div>
                  )}

                  {/* 对比结果 */}
                  {compareResult && (
                    <div className="mt-4">
                  {/* AI分析 */}
                  <div className="card mb-4" style={{borderColor: '#3b82f6'}}>
                    <div className="card-header">
                      <h4 className="card-title">🤖 AI分析</h4>
                    </div>
                    <div className="card-body">
                      <p className="text-gray-700">{compareResult.ai_analysis}</p>
                    </div>
                  </div>

                  {/* 统计 */}
                  <div className="grid-3 mb-4">
                    <div className="stat-card stat-card-mini" style={{borderColor: '#22c55e'}}>
                      <div className="stat-label">新增任务</div>
                      <div className="stat-value-lg" style={{color: '#22c55e'}}>{compareResult.summary.added_count}</div>
                    </div>
                    <div className="stat-card stat-card-mini" style={{borderColor: '#ef4444'}}>
                      <div className="stat-label">删除任务</div>
                      <div className="stat-value-lg" style={{color: '#ef4444'}}>{compareResult.summary.deleted_count}</div>
                    </div>
                    <div className="stat-card stat-card-mini" style={{borderColor: '#f59e0b'}}>
                      <div className="stat-label">修改任务</div>
                      <div className="stat-value-lg" style={{color: '#f59e0b'}}>{compareResult.summary.modified_count}</div>
                    </div>
                  </div>

                  {/* 新增任务 */}
                  {compareResult.added_tasks.length > 0 && (
                    <div className="card mb-4">
                      <div className="card-header">
                        <h4 className="card-title">➕ 新增任务</h4>
                      </div>
                      <div className="card-body">
                        <div className="space-y-2">
                          {compareResult.added_tasks.map((task, idx) => (
                            <div key={idx} className="p-3 bg-green-50 rounded-lg">
                              <div className="font-medium text-green-800">{task.task_name}</div>
                              <div className="text-sm text-green-600 mt-1">
                                {task.assignee && `负责人: ${task.assignee}`}
                                {task.start_date && ` | ${task.start_date} ~ ${task.end_date}`}
                                {task.planned_hours > 0 && ` | ${task.planned_hours}h`}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* 删除任务 */}
                  {compareResult.deleted_tasks.length > 0 && (
                    <div className="card mb-4">
                      <div className="card-header">
                        <h4 className="card-title">➖ 删除任务</h4>
                      </div>
                      <div className="card-body">
                        <div className="space-y-2">
                          {compareResult.deleted_tasks.map((task, idx) => (
                            <div key={idx} className="p-3 bg-red-50 rounded-lg">
                              <div className="font-medium text-red-800 line-through">{task.task_name}</div>
                              <div className="text-sm text-red-600 mt-1">
                                {task.assignee && `负责人: ${task.assignee}`}
                                {task.start_date && ` | ${task.start_date} ~ ${task.end_date}`}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* 修改任务 */}
                  {compareResult.modified_tasks.length > 0 && (
                    <div className="card">
                      <div className="card-header">
                        <h4 className="card-title">✏️ 修改任务</h4>
                      </div>
                      <div className="card-body">
                        <div className="space-y-2">
                          {compareResult.modified_tasks.map((task, idx) => (
                            <div key={idx} className="p-3 bg-yellow-50 rounded-lg">
                              <div className="font-medium text-yellow-800">{task.task_name}</div>
                              <div className="text-sm text-yellow-600 mt-1">
                                {task.changes.map((c, i) => (
                                  <div key={i}>• {c}</div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
                </>
              )}
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowCompareModal(false)} className="btn btn-secondary">
                关闭
              </button>
            </div>
          </div>
        </div>
      )}


      {/* Excel预览模态框 */}
      {previewVersion && (
        <div className="modal-overlay" onClick={() => setPreviewVersion(null)}>
          <div className="modal-content" style={{ maxWidth: '90%', width: '1200px', maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">📊 Excel预览 - {previewVersion.file_name}</h3>
              <button className="modal-close" onClick={() => setPreviewVersion(null)}>×</button>
            </div>
            <div className="modal-body" style={{ maxHeight: '75vh', overflow: 'auto' }}>
              {isLoadingPreview ? (
                <div className="empty-state" style={{ padding: '40px' }}>
                  <span className="spinner"></span>
                  <p className="mt-4 text-gray-500">正在加载Excel...</p>
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* 移动端底部导航 */}
      <MobileNav active="projects" />
    </div>
  )
}
