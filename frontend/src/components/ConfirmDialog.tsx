import type { ReactNode } from 'react'

interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  type?: 'danger' | 'warning' | 'info'
}

// 全局状态
let confirmResolver: ((value: boolean) => void) | null = null

// 导出 confirm 函数
export function confirm(options: ConfirmOptions): Promise<boolean> {
  console.log('[ConfirmDialog] confirm called with:', options.title)
  
  // 直接更新 DOM（绕过 React 状态）
  const dialogEl = document.getElementById('confirm-dialog-container')
  if (dialogEl) {
    dialogEl.style.display = 'flex'
    const titleEl = document.getElementById('confirm-dialog-title')
    const messageEl = document.getElementById('confirm-dialog-message')
    const confirmBtn = document.getElementById('confirm-dialog-confirm')
    const cancelBtn = document.getElementById('confirm-dialog-cancel')
    const contentEl = document.getElementById('confirm-dialog-content')
    
    if (titleEl) titleEl.textContent = options.title
    if (messageEl) messageEl.textContent = options.message
    if (confirmBtn) confirmBtn.textContent = options.confirmText || '确定'
    if (cancelBtn) cancelBtn.textContent = options.cancelText || '取消'
    
    // 设置边框颜色
    if (contentEl) {
      const color = options.type === 'danger' ? '#ef4444' : options.type === 'warning' ? '#eab308' : '#3b82f6'
      contentEl.style.borderLeftColor = color
    }
  }
  
  return new Promise((resolve) => {
    confirmResolver = resolve
  })
}

// 处理结果
function handleResult(result: boolean) {
  console.log('[ConfirmDialog] handleResult:', result)
  const dialogEl = document.getElementById('confirm-dialog-container')
  if (dialogEl) {
    dialogEl.style.display = 'none'
  }
  if (confirmResolver) {
    confirmResolver(result)
    confirmResolver = null
  }
}

// 全局函数
(window as any).confirmDialogResult = handleResult

export function ConfirmProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      
      {/* 直接渲染到 DOM */}
      <div 
        id="confirm-dialog-container"
        style={{ 
          display: 'none', 
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 9999,
          alignItems: 'center', 
          justifyContent: 'center' 
        }}
      >
        {/* 背景遮罩 */}
        <div 
          style={{ 
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(4px)'
          }}
          onClick={() => handleResult(false)}
        />
        
        {/* 弹窗内容 */}
        <div 
          id="confirm-dialog-content"
          style={{ 
            position: 'relative',
            backgroundColor: 'white',
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            maxWidth: '400px',
            width: '100%',
            margin: '0 16px',
            borderLeftWidth: '4px',
            borderLeftColor: '#eab308'
          }}
        >
          <div style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <span style={{ fontSize: '20px', marginTop: '2px' }}>⚡</span>
              <div style={{ flex: 1 }}>
                <h3 id="confirm-dialog-title" style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: 0 }}>确认</h3>
                <p id="confirm-dialog-message" style={{ marginTop: '4px', fontSize: '14px', color: '#4b5563', margin: 0 }}>消息</p>
              </div>
            </div>
            
            <div style={{ marginTop: '20px', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                id="confirm-dialog-cancel"
                style={{ 
                  padding: '8px 16px', 
                  fontSize: '14px', 
                  fontWeight: 500, 
                  color: '#374151', 
                  backgroundColor: '#f3f4f6', 
                  borderRadius: '8px',
                  border: 'none',
                  cursor: 'pointer'
                }}
                onClick={() => handleResult(false)}
              >
                取消
              </button>
              <button
                id="confirm-dialog-confirm"
                style={{ 
                  padding: '8px 16px', 
                  fontSize: '14px', 
                  fontWeight: 500, 
                  color: 'white', 
                  backgroundColor: '#d97706', 
                  borderRadius: '8px',
                  border: 'none',
                  cursor: 'pointer'
                }}
                onClick={() => handleResult(true)}
              >
                确定
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
