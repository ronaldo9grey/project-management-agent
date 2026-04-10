import { Link } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useRef, useEffect } from 'react'
import { useAppStore } from '../store'
import { chatApi } from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  time: string
}

export default function ChatPage() {
  const { user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '你好！我是项目智能助手，可以帮你查询项目状态、任务进度、工时统计等。有什么我可以帮助你的？',
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
  ])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 快捷问题
  const quickQuestions = [
    { icon: '📋', text: '我本周任务' },
    { icon: '⚠️', text: '哪些项目有延期风险' },
    { icon: '📊', text: '我的工时统计' },
    { icon: '🎯', text: '我的目标进度' },
  ]

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = async (text?: string) => {
    const messageText = text || inputText.trim()
    if (!messageText || isLoading) return

    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content: messageText,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    setMessages(prev => [...prev, userMessage])
    setInputText('')
    setIsLoading(true)

    try {
      const result = await chatApi.chat(messageText)
      
      // 添加助手消息
      const assistantMessage: Message = {
        role: 'assistant',
        content: result.response,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error: any) {
      const errorMessage: Message = {
        role: 'assistant',
        content: '抱歉，查询出现问题，请稍后重试。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  return (
    <div className="page-container chat-page">
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
              <Link to="/chat" className="nav-link active">问答</Link>
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

      {/* 聊天区域 */}
      <main className="chat-container">
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              <div className="chat-avatar">
                {msg.role === 'user' ? (user?.name?.[0]?.toUpperCase() || 'U') : '🤖'}
              </div>
              <div className="chat-content">
                <div className="chat-header">
                  <span className="chat-name">
                    {msg.role === 'user' ? user?.name : '智能助手'}
                  </span>
                  <span className="chat-time">{msg.time}</span>
                </div>
                <div className="chat-bubble">
                  <div className="chat-text" style={{whiteSpace: 'pre-wrap'}}>{msg.content}</div>
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="chat-message assistant">
              <div className="chat-avatar">🤖</div>
              <div className="chat-content">
                <div className="chat-bubble">
                  <div className="chat-loading">
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* 快捷问题 */}
        <div className="chat-quick-actions">
          {quickQuestions.map((q, idx) => (
            <button
              key={idx}
              className="quick-question-btn"
              onClick={() => sendMessage(q.text)}
              disabled={isLoading}
            >
              <span>{q.icon}</span>
              <span>{q.text}</span>
            </button>
          ))}
        </div>

        {/* 输入区域 */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，如：600KA槽项目进度如何？"
              className="chat-input"
              rows={1}
              disabled={isLoading}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!inputText.trim() || isLoading}
              className="chat-send-btn"
            >
              {isLoading ? '...' : '发送'}
            </button>
          </div>
        </div>
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="dashboard" />
    </div>
  )
}
