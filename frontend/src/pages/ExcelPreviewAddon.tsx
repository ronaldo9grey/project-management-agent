// Plans.tsx Excel预览功能补充代码

// 1. 在版本列表项中添加文件名显示和点击预览
{v.file_name && (
  <span 
    className="text-blue-600 cursor-pointer hover:underline text-xs"
    onClick={() => handlePreviewExcel(v)}
    title="点击预览Excel"
  >
    📊 {v.file_name}
  </span>
)}

// 2. 添加预览函数
const handlePreviewExcel = async (version: PlanVersion) => {
  if (!version.file_name) {
    alert('该版本没有关联的Excel文件')
    return
  }
  
  setPreviewVersion(version)
  setIsLoadingPreview(true)
  setPreviewHtml('')
  
  try {
    const response = await fetch(`/api/agent/plans/file/${version.id}`, {
      headers: {
        'Authorization': `Bearer ${useAppStore.getState().token}`
      }
    })
    
    if (!response.ok) {
      throw new Error('文件不存在或已删除')
    }
    
    const blob = await response.blob()
    const data = await blob.arrayBuffer()
    const workbook = XLSX.read(data, { type: 'array' })
    const sheet = workbook.Sheets[workbook.SheetNames[0]]
    
    const html = XLSX.utils.sheet_to_html(sheet, {
      editable: false,
      header: `<table style="border-collapse: collapse; width: 100%; font-size: 12px;">`,
      footer: '</table>'
    })
    
    const styledHtml = html
      .replace(/<td/g, '<td style="border: 1px solid #e5e7eb; padding: 4px 8px;"')
      .replace(/<th/g, '<th style="border: 1px solid #e5e7eb; padding: 4px 8px; background: #f3f4f6; font-weight: 600;"')
    
    setPreviewHtml(styledHtml)
  } catch (error: any) {
    alert(`预览失败: ${error.message}`)
  } finally {
    setIsLoadingPreview(false)
  }
}

// 3. 添加预览模态框（放在文件末尾）
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
