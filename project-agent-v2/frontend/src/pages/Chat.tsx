import SharedHeader from '../components/SharedHeader'
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
  const { user } = useAppStore()
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


  return (
    <div className="page-container chat-page">
      {/* 顶部导航 */}
      <SharedHeader />

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
