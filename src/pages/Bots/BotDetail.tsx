import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Bot, MessageSquare, Book, Image } from 'lucide-react'
import Button from '../../components/common/Button'
import TrainingTab from './TrainingTab'
import KnowledgeTab from './KnowledgeTab'
import MaterialTab from './MaterialTab'
import './BotDetail.css'

interface Bot {
  id: string
  name: string
  project: string
  status: string
  workflow: string
  tone: string
  score: number
}

const TABS = [
  { id: 'training', label: '训练对话', icon: MessageSquare },
  { id: 'knowledge', label: '知识内容', icon: Book },
  { id: 'material', label: '素材内容', icon: Image },
]

export default function BotDetailPage() {
  const { botId } = useParams<{ botId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('training')
  const [bot, setBot] = useState<Bot | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadBot()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId])

  const loadBot = async () => {
    try {
      // TODO: 替换为真实 API（botsApi.getById）
      setBot({
        id: botId ?? '',
        name: '美妆销售顾问',
        project: 'GlowLab',
        status: 'online',
        workflow: '销售接待主流程',
        tone: '亲切专业',
        score: 92,
      })
    } catch (error) {
      console.error('加载机器人失败:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="page-loading">加载中...</div>
  }

  if (!bot) {
    return <div className="page-loading">机器人不存在</div>
  }

  return (
    <div className="bot-detail-page">
      <div className="detail-header">
        <Button
          variant="ghost"
          size="sm"
          icon={<ArrowLeft size={16} />}
          onClick={() => navigate('/bots')}
        >
          返回
        </Button>

        <div className="detail-header-info">
          <div className="detail-avatar">
            <Bot size={24} />
          </div>
          <div className="detail-meta">
            <h2 className="detail-name">{bot.name}</h2>
            <div className="detail-tags">
              <span className="detail-tag">{bot.project}</span>
              <span className="detail-tag">{bot.workflow}</span>
              <span className={`detail-status status-${bot.status}`}>
                {bot.status === 'online' ? '在线' : '训练中'}
              </span>
            </div>
          </div>
        </div>

        <div className="detail-actions">
          <Button variant="secondary" size="sm">
            查看数据
          </Button>
          <Button variant="primary" size="sm">
            发布上线
          </Button>
        </div>
      </div>

      <div className="detail-tabs">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              type="button"
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      <div className="detail-content">
        {activeTab === 'training' && <TrainingTab bot={bot} />}
        {activeTab === 'knowledge' && <KnowledgeTab bot={bot} />}
        {activeTab === 'material' && <MaterialTab bot={bot} />}
      </div>
    </div>
  )
}
