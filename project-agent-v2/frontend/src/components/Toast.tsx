import { useState, useCallback, createContext, useContext, type ReactNode } from 'react'

interface ToastState {
  message: string
  type: 'error' | 'success' | 'warning' | 'info'
  id: number
}

interface ToastContextType {
  showToast: (message: string, type?: ToastState['type']) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let toastId = 0

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    // 降级：返回一个空函数，避免崩溃
    console.warn('ToastContext not available')
    return { showToast: (msg: string) => console.error('[Toast]', msg) }
  }
  return context
}

// 全局引用（用于非 React 上下文调用，如 api.ts）
let globalShowToast: ((message: string, type?: ToastState['type']) => void) | null = null

export function showToast(message: string, type: ToastState['type'] = 'error') {
  if (globalShowToast) {
    globalShowToast(message, type)
  } else {
    // 降级：只打印日志，不使用 alert
    console.error('[Toast]', message)
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const add = useCallback((message: string, type: ToastState['type'] = 'error') => {
    const id = ++toastId
    setToasts(prev => [...prev, { message, type, id }])
    
    // 5 秒后自动消失
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  // 注册全局引用
  globalShowToast = add

  const removeToast = (id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  const typeStyles = {
    error: 'bg-red-50 border-red-200 text-red-800',
    success: 'bg-green-50 border-green-200 text-green-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  }

  const typeIcons = {
    error: '❌',
    success: '✅',
    warning: '⚠️',
    info: 'ℹ️',
  }

  return (
    <ToastContext.Provider value={{ showToast: add }}>
      {children}
      {toasts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
          {toasts.map(toast => (
            <div
              key={toast.id}
              className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg animate-slide-in ${typeStyles[toast.type]}`}
              onClick={() => removeToast(toast.id)}
              style={{ cursor: 'pointer' }}
            >
              <span className="text-lg">{typeIcons[toast.type]}</span>
              <span className="flex-1 text-sm font-medium">{toast.message}</span>
              <button
                className="text-current opacity-60 hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation()
                  removeToast(toast.id)
                }}
              >
                ✕
              </button>
            </div>
          ))}
          <style>{`
            @keyframes slide-in {
              from {
                transform: translateX(100%);
                opacity: 0;
              }
              to {
                transform: translateX(0);
                opacity: 1;
              }
            }
            .animate-slide-in {
              animation: slide-in 0.3s ease-out;
            }
          `}</style>
        </div>
      )}
    </ToastContext.Provider>
  )
}

// 默认导出兼容旧代码
export default function Toast() {
  return null // 现在使用 ToastProvider，此组件不再需要
}
