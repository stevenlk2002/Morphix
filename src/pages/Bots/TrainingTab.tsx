import { useState } from 'react'
import { Send, ThumbsUp, ThumbsDown, RefreshCw } from 'lucide-react'
import Button from '../../components/common/Button'
import './TrainingTab.css'

interface BotRef {
  id: string
  name?: string
}

interface Message {
  id: number
  role: 'user' | 'ai'
  content: string
  score?: number
}

interface Suggestion {
  type: 'good' | 'improve'
  text: string
}

const MOCK_MESSAGES: Message[] = [
  { id: 1, role: 'user', content: '你好，我想了解一下你们的产品' },
  {
    id: 2,
    role: 'ai',
    content:
      '您好！很高兴为您介绍。我们的产品线覆盖护肤、彩妆和个护三大类，您对哪一类比较感兴趣呢？',
    score: 92,
  },
  { id: 3, role: 'user', content: '我是敏感肌，有什么推荐的护肤品吗？' },
  {
    id: 4,
    role: 'ai',
    content:
      '针对敏感肌，我推荐我们的舒缓修护系列，成分温和无刺激，特别添加了积雪草和神经酰胺，可以有效舒缓肌肤、修复屏障。目前正在做买二送一活动，您需要了解详细信息吗？',
    score: 88,
  },
]

const SUGGESTIONS: Suggestion[] = [
  { type: 'good', text: '准确识别了用户的敏感肌需求' },
  { type: 'good', text: '主动推荐了促销活动信息' },
  { type: 'improve', text: '可以追问用户具体的肌肤问题，提供更精准的方案' },
  { type: 'improve', text: '建议补充产品的真实用户评价，增强信任感' },
]

export default function TrainingTab({ bot }: { bot: BotRef }) {
  const [messages, setMessages] = useState<Message[]>(MOCK_MESSAGES)
  const [input, setInput] = useState('')

  const handleSend = () => {
    if (!input.trim()) return

    const newMessage: Message = {
      id: messages.length + 1,
      role: 'user',
      content: input,
    }

    setMessages([...messages, newMessage])
    setInput('')

    setTimeout(() => {
      const aiResponse: Message = {
        id: messages.length + 2,
        role: 'ai',
        content: '好的，我明白了。让我为您提供更详细的信息...',
        score: 85,
      }
      setMessages((prev) => [...prev, aiResponse])
    }, 1000)
  }

  const handleReset = () => {
    setMessages(MOCK_MESSAGES)
    setInput('')
  }

  return (
    <div className="training-tab">
      <div className="training-main">
        <div className="training-header">
          <h3 className="training-title">模拟训练对话</h3>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={14} />}
            onClick={handleReset}
          >
            重置对话
          </Button>
        </div>

        <div className="training-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`message message-${msg.role}`}>
              <div className="message-avatar">{msg.role === 'user' ? '客' : 'AI'}</div>
              <div className="message-content">
                <div className="message-text">{msg.content}</div>
                {msg.role === 'ai' && msg.score && (
                  <div className="message-meta">
                    <span className="message-score">得分: {msg.score}</span>
                    <button type="button" className="message-action">
                      <ThumbsUp size={14} />
                    </button>
                    <button type="button" className="message-action">
                      <ThumbsDown size={14} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="training-input">
          <input
            type="text"
            placeholder="输入客户消息，测试机器人回复..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <Button
            variant="primary"
            size="sm"
            icon={<Send size={16} />}
            onClick={handleSend}
            disabled={!input.trim()}
          >
            发送
          </Button>
        </div>
      </div>

      <div className="training-sidebar">
        <h3 className="sidebar-title">调优建议</h3>
        <div className="suggestions">
          {SUGGESTIONS.map((item, index) => (
            <div key={index} className={`suggestion suggestion-${item.type}`}>
              <span className="suggestion-icon">{item.type === 'good' ? '✓' : '!'}</span>
              <span className="suggestion-text">{item.text}</span>
            </div>
          ))}
        </div>

        <div className="training-stats">
          <h4 className="stats-title">本轮统计</h4>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">回复轮次</div>
              <div className="stat-value">{Math.floor(messages.length / 2)}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">平均得分</div>
              <div className="stat-value">90</div>
            </div>
          </div>
        </div>
        <div className="training-bot-name text-secondary">
          当前训练对象：{bot.name ?? bot.id}
        </div>
      </div>
    </div>
  )
}
