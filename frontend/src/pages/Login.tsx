import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import { useAppStore } from '../store'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setToken, setUser } = useAppStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [shake, setShake] = useState(false)
  
  // 用户名输入框引用
  const usernameInputRef = useRef<HTMLInputElement>(null)
  
  // 页面加载时自动聚焦到用户名输入框，并恢复记住的用户名
  useEffect(() => {
    const savedUsername = localStorage.getItem('remembered_username')
    if (savedUsername) {
      setUsername(savedUsername)
      setRememberMe(true)
    }
    usernameInputRef.current?.focus()
  }, [])

  // 触发错误抖动动画
  const triggerShake = () => {
    setShake(true)
    setTimeout(() => setShake(false), 500)
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('请输入用户名和密码')
      triggerShake()
      return
    }

    setIsLoading(true)
    setError('')

    try {
      const result = await authApi.login(username, password)
      if (result.access_token) {
        // 记住用户名
        if (rememberMe) {
          localStorage.setItem('remembered_username', username)
        } else {
          localStorage.removeItem('remembered_username')
        }
        
        // 构建用户信息
        let userData: any = {
          id: username,
          name: username,
          username: username,
        }
        
        if (result.user && result.user.name) {
          userData = {
            id: result.user.id || username,
            name: result.user.name,
            username: result.user.username || username,
            role_id: result.user.role_id,
            employee_id: result.user.id,
          }
        } else {
          // 尝试获取用户信息
          try {
            const userInfo = await authApi.getUserInfo()
            userData = {
              id: userInfo.employee_id || username,
              name: userInfo.name || username,
              username: userInfo.username || username,
              employee_id: userInfo.employee_id,
              department: userInfo.department,
              position: userInfo.position,
              phone: userInfo.phone,
              email: userInfo.email,
              role_id: userInfo.role_id,
              role_name: userInfo.role_name,
              permissions: userInfo.permissions?.allowed_modules || [],
            }
          } catch {}
        }
        
        // 更新 zustand store（会自动同步到 localStorage）
        setToken(result.access_token)
        setUser(userData)
        
        // 等待状态更新完成后再导航
        setTimeout(() => {
          navigate('/')
        }, 100)
      } else {
        setError('登录失败，请检查用户名和密码')
        triggerShake()
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || '登录失败，请检查用户名和密码'
      setError(errorMsg)
      console.error('登录失败:', err)
      triggerShake()
      // 登录失败后聚焦到密码输入框，方便重新输入
      setTimeout(() => {
        const passwordInput = document.querySelector('input[type="password"], input[type="text"][placeholder*="密码"]') as HTMLInputElement
        passwordInput?.focus()
        passwordInput?.select()
      }, 100)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-container">
      {/* 左侧装饰区域 - 仅PC端显示 */}
      <div className="login-decoration">
        <div className="decoration-content">
          <div className="decoration-icon">⚙️</div>
          <h2 className="decoration-title">项目管家</h2>
          <p className="decoration-desc">
            AI驱动的项目管理助手<br />
            智能解析 · 自动匹配 · 高效协作
          </p>
          <div className="decoration-features">
            <div className="feature-item">
              <span className="feature-icon">📝</span>
              <span>智能日报解析</span>
            </div>
            <div className="feature-item">
              <span className="feature-icon">🎯</span>
              <span>项目自动匹配</span>
            </div>
            <div className="feature-item">
              <span className="feature-icon">📊</span>
              <span>工时进度追踪</span>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧登录区域 */}
      <div className="login-form-section">
        <div className="login-form-wrapper">
          {/* 移动端Logo */}
          <div className="login-logo-mobile">
            <div className="logo-icon-mobile">⚙️</div>
            <h1 className="logo-title-mobile">项目管家</h1>
          </div>

          <div className="login-header">
            <h1 className="login-title">欢迎回来</h1>
            <p className="login-subtitle">请登录您的账号</p>
          </div>

          {/* 登录卡片 */}
          <div className={`login-card ${shake ? 'shake' : ''}`}>
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label className="form-label">用户名</label>
                <input
                  ref={usernameInputRef}
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入工号或用户名"
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">密码</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    className="form-input"
                    style={{ paddingRight: '44px' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '18px',
                      color: '#9ca3af',
                      padding: '4px'
                    }}
                  >
                    {showPassword ? '👁️' : '👁️‍🗨️'}
                  </button>
                </div>
              </div>

              {/* 记住我 */}
              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px', color: '#6b7280' }}>
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    style={{ width: '16px', height: '16px', borderRadius: '4px' }}
                  />
                  记住用户名
                </label>
              </div>

              {error && (
                <div className="form-error" style={{
                  padding: '12px 16px',
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '8px',
                  color: '#dc2626',
                  fontSize: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span style={{fontSize: '16px'}}>⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="login-btn"
              >
                {isLoading ? (
                  <span className="login-loading">
                    <span className="spinner"></span>
                    登录中...
                  </span>
                ) : (
                  '登录'
                )}
              </button>
            </form>
          </div>

          <div className="login-footer">
            <p>使用现有管理系统账号登录</p>
          </div>
        </div>
      </div>
    </div>
  )
}
