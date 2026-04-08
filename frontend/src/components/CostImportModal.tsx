import { useState } from 'react'
import { useAppStore } from '../store'

// 飞书 SDK 类型声明
declare global {
  interface Window {
    h5sdk?: {
      config: (config: {
        appId: string;
        timestamp: number;
        nonceStr: string;
        signature: string;
        jsApiList: string[];
        onSuccess?: () => void;
        onFail?: (err: any) => void;
      }) => void;
      biz: {
        util: {
          chooseFile: (config: {
            maxNum: number;
            type: string;
            onSuccess: (result: { fileList: Array<{ name: string; path: string; size: number }> }) => void;
            onFail?: (err: any) => void;
          }) => void;
        };
      };
      ready: (callback: () => void) => void;
    };
  }
}

interface CostImportModalProps {
  projectId?: string
  projectName?: string
  onClose: () => void
  onSuccess: () => void
}

interface FileInfo {
  sheets: string[]
  columns: { [sheet: string]: string[] }
  sample_data: { [sheet: string]: any[] }
  row_count: { [sheet: string]: number }
}

interface ColumnMapping {
  project_column: string | null
  amount_column: string | null
  cost_type: string | null
  cost_subtype: string | null
  date_column: string | null
  description_column: string | null
  quantity_column: string | null
  unit_price_column: string | null
  confidence: number
}

interface PreviewData {
  total_rows: number
  matched_projects: Array<{ name: string; project_id: string }>
  unmatched_projects: string[]
  preview_data: Array<{ row: number; project: string; matched_project_id: string; amount: number }>
}

export default function CostImportModal({ onClose, onSuccess }: CostImportModalProps) {
  const [step, setStep] = useState(1) // 1: 上传, 2: 分析, 3: 预览, 4: 完成
  const [file, setFile] = useState<File | null>(null)
  const [fileContent, setFileContent] = useState<number[]>([])
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null)
  const [selectedSheet, setSelectedSheet] = useState<string>('')
  const [columnMapping, setColumnMapping] = useState<ColumnMapping | null>(null)
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [costType, setCostType] = useState<string>('')
  const [costSubtype, setCostSubtype] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string>('')
  
  // 检测是否在飞书环境
  const isInFeishu = () => {
    return /Lark|Feishu/i.test(navigator.userAgent) || typeof window.h5sdk !== 'undefined'
  }
  
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return
    
    // 验证文件类型
    const fileName = selectedFile.name.toLowerCase()
    if (!fileName.endsWith('.xlsx') && !fileName.endsWith('.xls')) {
      setError('请选择 Excel 文件 (.xlsx 或 .xls)')
      return
    }
    
    setFile(selectedFile)
    setError('')
    
    // 读取文件内容
    const reader = new FileReader()
    reader.onload = async () => {
      const arrayBuffer = reader.result as ArrayBuffer
      const uint8Array = new Uint8Array(arrayBuffer)
      setFileContent(Array.from(uint8Array))
      
      // 分析文件
      await analyzeFile(Array.from(uint8Array), selectedFile.name)
    }
    reader.readAsArrayBuffer(selectedFile)
  }
  
  const analyzeFile = async (content: number[], fileName: string) => {
    setIsLoading(true)
    setError('')
    
    try {
      const formData = new FormData()
      const blob = new Blob([new Uint8Array(content)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      formData.append('file', blob, fileName)
      
      const token = useAppStore.getState().token
      const response = await fetch('/api/agent/cost/import/analyze', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })
      
      const result = await response.json()
      
      if (result.success) {
        setFileInfo(result.data)
        setSelectedSheet(result.data.sheets[0] || '')
        setStep(2)
      } else {
        setError(result.detail || '分析失败')
      }
    } catch (err: any) {
      setError(err.message || '网络错误')
    } finally {
      setIsLoading(false)
    }
  }
  
  const identifyColumns = async () => {
    if (!fileInfo || !selectedSheet) return
    
    setIsLoading(true)
    setError('')
    
    try {
      const token = useAppStore.getState().token
      const response = await fetch('/api/agent/cost/import/identify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          columns: fileInfo.columns[selectedSheet],
          sample_data: fileInfo.sample_data[selectedSheet]
        })
      })
      
      const result = await response.json()
      
      if (result.success) {
        setColumnMapping(result.data)
        setCostType(result.data.cost_type || '')
        setCostSubtype(result.data.cost_subtype || '')
      } else {
        setError(result.detail || '识别失败')
      }
    } catch (err: any) {
      setError(err.message || '网络错误')
    } finally {
      setIsLoading(false)
    }
  }
  
  const previewImport = async () => {
    if (!fileInfo || !selectedSheet || !columnMapping) return
    
    setIsLoading(true)
    setError('')
    
    try {
      const token = useAppStore.getState().token
      const response = await fetch('/api/agent/cost/import/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          file_content: fileContent,
          file_name: file?.name,
          sheet_name: selectedSheet,
          column_mapping: columnMapping
        })
      })
      
      const result = await response.json()
      
      if (result.success) {
        setPreviewData(result.data)
        setStep(3)
      } else {
        setError(result.detail || '预览失败')
      }
    } catch (err: any) {
      setError(err.message || '网络错误')
    } finally {
      setIsLoading(false)
    }
  }
  
  const executeImport = async () => {
    if (!fileInfo || !selectedSheet || !columnMapping || !costType) return
    
    setIsLoading(true)
    setError('')
    
    try {
      const token = useAppStore.getState().token
      const response = await fetch('/api/agent/cost/import/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          file_content: fileContent,
          file_name: file?.name,
          sheet_name: selectedSheet,
          column_mapping: columnMapping,
          cost_type: costType,
          cost_subtype: costSubtype
        })
      })
      
      const result = await response.json()
      
      if (result.success) {
        setStep(4)
        onSuccess()
      } else {
        setError(result.detail || '导入失败')
      }
    } catch (err: any) {
      setError(err.message || '网络错误')
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">📊 成本数据智能导入</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-body">
          {/* 步骤指示器 */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
            {[1, 2, 3, 4].map(s => (
              <div key={s} style={{
                flex: 1,
                height: '4px',
                borderRadius: '2px',
                background: s <= step ? '#3b82f6' : '#e5e7eb',
                transition: 'background 0.3s'
              }} />
            ))}
          </div>
          
          {error && (
            <div style={{
              padding: '12px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              color: '#dc2626',
              marginBottom: '16px'
            }}>
              ❌ {error}
            </div>
          )}
          
          {/* 步骤1：上传文件 */}
          {step === 1 && (
            <div className="text-center py-8">
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>📁</div>
              <p className="text-gray-600 mb-4">支持 Excel 格式 (.xlsx, .xls)</p>
              
              {isInFeishu() ? (
                // 飞书环境：显示提示和链接输入
                <div>
                  <div style={{
                    padding: '16px',
                    background: '#fef3c7',
                    borderRadius: '8px',
                    marginBottom: '16px',
                    fontSize: '14px',
                    color: '#92400e'
                  }}>
                    💡 手机端请先将文件上传到飞书云盘，然后粘贴分享链接
                  </div>
                  
                  <div className="form-group" style={{ textAlign: 'left' }}>
                    <label className="form-label">文件链接</label>
                    <input
                      type="text"
                      placeholder="粘贴飞书云盘文件链接..."
                      className="input"
                      style={{ fontSize: '14px' }}
                      onChange={async (e) => {
                        const link = e.target.value.trim()
                        if (!link) return
                        
                        setIsLoading(true)
                        setError('')
                        
                        try {
                          const token = useAppStore.getState().token
                          const response = await fetch('/api/agent/cost/import/from-link', {
                            method: 'POST',
                            headers: {
                              'Content-Type': 'application/json',
                              'Authorization': `Bearer ${token}`
                            },
                            body: JSON.stringify({ file_link: link })
                          })
                          
                          const data = await response.json()
                          
                          if (data.success) {
                            setFileContent(data.content)
                            setFileInfo(data.file_info)
                            setSelectedSheet(data.file_info.sheets[0] || '')
                            setFile({ name: data.file_name } as File)
                            setStep(2)
                          } else {
                            setError(data.detail || '文件读取失败')
                          }
                        } catch (err: any) {
                          setError(err.message || '网络错误')
                        } finally {
                          setIsLoading(false)
                        }
                      }}
                    />
                  </div>
                  
                  <button
                    disabled={isLoading}
                    style={{
                      marginTop: '16px',
                      padding: '12px 32px',
                      background: isLoading ? '#93c5fd' : '#3b82f6',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '500',
                      cursor: isLoading ? 'not-allowed' : 'pointer'
                    }}
                    onClick={() => setError('请先在上方输入框粘贴文件链接')}
                  >
                    {isLoading ? '⏳ 处理中...' : '📤 导入文件'}
                  </button>
                </div>
              ) : (
                // 非飞书环境：自定义样式的文件选择按钮
                <div>
                  <div style={{
                    position: 'relative',
                    display: 'inline-block'
                  }}>
                    <input
                      type="file"
                      accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      onChange={handleFileSelect}
                      disabled={isLoading}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        opacity: 0,
                        cursor: 'pointer'
                      }}
                    />
                    <div style={{
                      padding: '14px 28px',
                      background: isLoading ? '#93c5fd' : '#3b82f6',
                      color: 'white',
                      borderRadius: '8px',
                      fontSize: '16px',
                      fontWeight: '500',
                      pointerEvents: 'none'
                    }}>
                      📁 点击选择Excel文件
                    </div>
                  </div>
                  
                  {file && (
                    <div style={{ marginTop: '16px', color: '#16a34a', fontSize: '14px' }}>
                      ✅ 已选择: {file.name}
                    </div>
                  )}
                </div>
              )}
              
              {isLoading && !isInFeishu() && (
                <div style={{ marginTop: '16px', color: '#3b82f6' }}>
                  ⏳ 正在分析文件...
                </div>
              )}
              
              {file && !isLoading && !isInFeishu() && (
                <div style={{ marginTop: '16px', color: '#16a34a' }}>
                  ✅ 已选择: {file.name}
                </div>
              )}
            </div>
          )}
          
          {/* 步骤2：分析结果 */}
          {step === 2 && fileInfo && (
            <div>
              <h4 style={{ marginBottom: '16px', fontWeight: '600' }}>📋 文件分析结果</h4>
              
              {/* 工作表选择 */}
              <div className="form-group">
                <label className="form-label">选择工作表</label>
                <select
                  value={selectedSheet}
                  onChange={e => setSelectedSheet(e.target.value)}
                  className="input"
                >
                  {fileInfo.sheets.map(s => (
                    <option key={s} value={s}>{s} ({fileInfo.row_count[s]} 行)</option>
                  ))}
                </select>
              </div>
              
              {/* 列信息 */}
              {selectedSheet && (
                <>
                  <div style={{ marginBottom: '16px' }}>
                    <label className="form-label">检测到的列</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                      {fileInfo.columns[selectedSheet].map((col, idx) => (
                        <span key={idx} style={{
                          padding: '4px 12px',
                          background: '#f1f5f9',
                          borderRadius: '12px',
                          fontSize: '12px',
                          color: '#475569'
                        }}>
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* AI识别按钮 */}
                  <button
                    onClick={identifyColumns}
                    className="btn btn-primary"
                    disabled={isLoading}
                    style={{ width: '100%' }}
                  >
                    {isLoading ? '⏳ AI识别中...' : '🤖 AI智能识别列含义'}
                  </button>
                  
                  {/* 识别结果 */}
                  {columnMapping && (
                    <div style={{ marginTop: '16px', padding: '16px', background: '#f0fdf4', borderRadius: '8px' }}>
                      <h5 style={{ marginBottom: '12px', color: '#16a34a' }}>✅ 识别结果 (置信度: {(columnMapping.confidence * 100).toFixed(0)}%)</h5>
                      
                      <div style={{ display: 'grid', gap: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b' }}>项目列:</span>
                          <span style={{ fontWeight: '500' }}>{columnMapping.project_column || '-'}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b' }}>金额列:</span>
                          <span style={{ fontWeight: '500' }}>{columnMapping.amount_column || '-'}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b' }}>成本类型:</span>
                          <span style={{ fontWeight: '500' }}>
                            {columnMapping.cost_type === 'material' ? '材料成本' : 
                             columnMapping.cost_type === 'outsourcing' ? '外包成本' : 
                             columnMapping.cost_type === 'indirect' ? '间接成本' : '-'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#64748b' }}>具体类型:</span>
                          <span style={{ fontWeight: '500' }}>{columnMapping.cost_subtype || '-'}</span>
                        </div>
                      </div>
                      
                      {/* 手动调整 */}
                      <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px dashed #d1d5db' }}>
                        <h6 style={{ marginBottom: '8px', fontSize: '12px', color: '#64748b' }}>手动调整（可选）</h6>
                        
                        <div className="grid-2" style={{ gap: '12px' }}>
                          <div className="form-group" style={{ marginBottom: '8px' }}>
                            <label className="form-label" style={{ fontSize: '12px' }}>成本大类</label>
                            <select
                              value={costType}
                              onChange={e => setCostType(e.target.value)}
                              className="input"
                              style={{ fontSize: '13px' }}
                            >
                              <option value="">选择...</option>
                              <option value="material">材料成本</option>
                              <option value="outsourcing">外包成本</option>
                              <option value="indirect">间接成本</option>
                            </select>
                          </div>
                          
                          <div className="form-group" style={{ marginBottom: '8px' }}>
                            <label className="form-label" style={{ fontSize: '12px' }}>具体类型</label>
                            <input
                              type="text"
                              value={costSubtype}
                              onChange={e => setCostSubtype(e.target.value)}
                              className="input"
                              style={{ fontSize: '13px' }}
                              placeholder="如：差旅费、施工安装"
                            />
                          </div>
                        </div>
                      </div>
                      
                      <button
                        onClick={previewImport}
                        className="btn btn-primary"
                        disabled={isLoading || !costType}
                        style={{ width: '100%', marginTop: '16px' }}
                      >
                        {isLoading ? '⏳ 预览中...' : '👁️ 预览导入结果'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          
          {/* 步骤3：预览确认 */}
          {step === 3 && previewData && (
            <div>
              <h4 style={{ marginBottom: '16px', fontWeight: '600' }}>👁️ 导入预览</h4>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px' }}>
                <div style={{ padding: '16px', background: '#f0fdf4', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: '600', color: '#16a34a' }}>{previewData.total_rows}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>总行数</div>
                </div>
                <div style={{ padding: '16px', background: '#eff6ff', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: '600', color: '#3b82f6' }}>{previewData.matched_projects.length}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>匹配项目</div>
                </div>
                <div style={{ padding: '16px', background: '#fef2f2', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: '600', color: '#ef4444' }}>{previewData.unmatched_projects.length}</div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>未匹配</div>
                </div>
              </div>
              
              {/* 匹配的项目 */}
              {previewData.matched_projects.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <h5 style={{ fontSize: '13px', color: '#64748b', marginBottom: '8px' }}>✅ 匹配的项目</h5>
                  <div style={{ maxHeight: '150px', overflow: 'auto' }}>
                    {previewData.matched_projects.map((p, idx) => (
                      <div key={idx} style={{ padding: '8px 12px', background: '#f8fafc', borderRadius: '4px', marginBottom: '4px', fontSize: '13px' }}>
                        {p.name} → 项目ID: {p.project_id}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* 未匹配的项目 */}
              {previewData.unmatched_projects.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <h5 style={{ fontSize: '13px', color: '#dc2626', marginBottom: '8px' }}>⚠️ 未匹配的项目</h5>
                  <div style={{ padding: '12px', background: '#fef2f2', borderRadius: '8px', fontSize: '13px', color: '#991b1b' }}>
                    {previewData.unmatched_projects.join(', ')}
                  </div>
                  <p style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
                    这些项目将被跳过，请确保项目名称与系统中的项目名一致
                  </p>
                </div>
              )}
              
              {/* 操作按钮 */}
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={() => setStep(2)}
                  className="btn"
                  style={{ flex: 1, background: '#f1f5f9' }}
                >
                  返回调整
                </button>
                <button
                  onClick={executeImport}
                  className="btn btn-primary"
                  disabled={isLoading || previewData.matched_projects.length === 0}
                  style={{ flex: 2 }}
                >
                  {isLoading ? '⏳ 导入中...' : '✅ 确认导入'}
                </button>
              </div>
            </div>
          )}
          
          {/* 步骤4：完成 */}
          {step === 4 && (
            <div className="text-center py-8">
              <div style={{ fontSize: '64px', marginBottom: '16px' }}>✅</div>
              <h4 style={{ marginBottom: '8px' }}>导入完成</h4>
              <p className="text-gray-500 mb-4">成本数据已成功导入系统</p>
              
              <button onClick={onClose} className="btn btn-primary">
                关闭
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
