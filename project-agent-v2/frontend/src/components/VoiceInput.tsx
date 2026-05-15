import { useState, useEffect, useRef } from 'react'

interface VoiceInputProps {
  onTranscript: (text: string) => void
  disabled?: boolean
}

export default function VoiceInput({ onTranscript, disabled }: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false)
  const [isSupported, setIsSupported] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')
  const recognitionRef = useRef<any>(null)
  const onTranscriptRef = useRef(onTranscript)
  const isManualStopRef = useRef(false)

  // 保持 onTranscript 引用最新
  useEffect(() => {
    onTranscriptRef.current = onTranscript
  }, [onTranscript])

  useEffect(() => {
    // 检查是否是安全上下文（HTTPS 或 localhost）
    const isSecureContext = window.isSecureContext
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    
    if (!isSecureContext && !isLocalhost) {
      setIsSupported(false)
      console.log('语音识别需要 HTTPS 环境')
      return
    }

    // 检查浏览器支持
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      setIsSupported(false)
      console.log('浏览器不支持语音识别')
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    // 关闭连续模式，改为单次识别，避免 aborted 问题
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      console.log('语音识别已启动')
      setIsListening(true)
      setErrorMsg('')
    }

    recognition.onresult = (event: any) => {
      let text = ''
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript
      }
      console.log('语音识别结果:', text)
      if (text.trim()) {
        onTranscriptRef.current(text)
      }
    }

    recognition.onerror = (event: any) => {
      console.error('语音识别错误:', event.error, event)
      setIsListening(false)
      
      // aborted 错误通常是因为没有说话或说话太短
      if (event.error === 'aborted') {
        if (!isManualStopRef.current) {
          setErrorMsg('未检测到语音，请重试')
        }
      } else if (event.error === 'not-allowed') {
        setErrorMsg('请允许麦克风权限')
      } else if (event.error === 'no-speech') {
        setErrorMsg('未检测到语音')
      } else if (event.error === 'audio-capture') {
        setErrorMsg('未找到麦克风')
      } else if (event.error === 'network') {
        setErrorMsg('网络错误')
      } else {
        setErrorMsg(`错误: ${event.error}`)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
      console.log('语音识别结束')
      isManualStopRef.current = false
    }

    recognitionRef.current = recognition
    console.log('语音识别初始化成功')

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch (e) {
          // ignore
        }
      }
    }
  }, [])

  const toggleListening = () => {
    const isSecureContext = window.isSecureContext
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    
    if (!isSecureContext && !isLocalhost) {
      alert('⚠️ 语音识别需要 HTTPS 环境')
      return
    }

    if (!recognitionRef.current) {
      setErrorMsg('请刷新页面后重试')
      return
    }

    if (isListening) {
      // 手动停止
      isManualStopRef.current = true
      try {
        recognitionRef.current.stop()
      } catch (e) {
        console.error('停止识别失败:', e)
      }
      setIsListening(false)
      setErrorMsg('')
    } else {
      setErrorMsg('')
      isManualStopRef.current = false
      try {
        console.log('启动语音识别...')
        recognitionRef.current.start()
      } catch (e: any) {
        console.error('启动语音识别失败:', e)
        const errMsg = e?.toString() || ''
        if (errMsg.includes('already started')) {
          try {
            recognitionRef.current.stop()
          } catch (stopErr) {}
          setTimeout(() => {
            try {
              recognitionRef.current?.start()
            } catch (startErr) {
              setErrorMsg('启动失败，请重试')
            }
          }, 300)
        } else {
          setErrorMsg('启动失败，请重试')
        }
      }
    }
  }

  // 检查是否支持
  const isSecureContext = window.isSecureContext
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  
  if (!isSupported || (!isSecureContext && !isLocalhost)) {
    return (
      <button
        type="button"
        disabled
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          border: '2px solid #d1d5db',
          background: '#f3f4f6',
          cursor: 'not-allowed',
          opacity: 0.5,
        }}
        title="语音识别需要 HTTPS 环境"
      >
        <span style={{ fontSize: '20px', filter: 'grayscale(1)' }}>🎤</span>
      </button>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <button
        type="button"
        onClick={toggleListening}
        disabled={disabled}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          border: isListening ? '2px solid #ef4444' : '2px solid #d1d5db',
          background: isListening ? '#fef2f2' : 'white',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'all 0.3s ease',
          opacity: disabled ? 0.5 : 1,
          boxShadow: isListening ? '0 0 12px rgba(239, 68, 68, 0.5)' : 'none',
        }}
        title={isListening ? '点击停止' : '点击开始语音输入'}
      >
        {isListening ? (
          <span style={{ fontSize: '20px' }}>⏹️</span>
        ) : (
          <span style={{ fontSize: '20px' }}>🎤</span>
        )}
      </button>
      {isListening && (
        <span style={{ 
          fontSize: '11px', 
          color: '#ef4444', 
          marginTop: '4px',
          animation: 'pulse 1s infinite'
        }}>
          请说话...
        </span>
      )}
      {errorMsg && !isListening && (
        <span style={{ 
          fontSize: '10px', 
          color: '#64748b', 
          marginTop: '4px',
          maxWidth: '100px',
          textAlign: 'center'
        }}>
          💡 试试输入法语音
        </span>
      )}
    </div>
  )
}
