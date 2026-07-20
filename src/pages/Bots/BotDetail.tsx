import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Bot, MessageSquare, GitBranch } from 'lucide-react'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'
import TrainingTab from './TrainingTab'
import './BotDetail.css'

/** 机器人详情（mock 取数）。 */
interface Bot {
  id: string
  name: string
  project: string
  status: string
  workflow: string
  tone: string
  score: number
  desc: string
}

/** 传给三个 Tab 的引用对象。 */
interface BotRef {
  id: string
  name?: string
}

/** 按 id 取数的本地 mock 表。 */
const MOCK_BOTS: Record<string, Omit<Bot, 'id'>> = {
  yefengqiu: {
    name: '野风秋大健康机器人',
    project: '野风秋',
    workflow: '健康咨询主流程',
    status: 'online',
    tone: '专业亲切',
    score: 90,
    desc: '专注中老年群体及慢性病管理人群的科学、合规健康咨询与生活方式指导。',
  },
  fanfuni: {
    name: '梵芙尼美妆销售机器人',
    project: '梵芙尼',
    workflow: '美妆销售主流程',
    status: 'training',
    tone: '时尚专业',
    score: 76,
    desc: '为高端美妆消费者提供专业、个性化的护肤与彩妆产品咨询与购买引导。',
  },
}

/** 兜底机器人（未知 id 时使用）。 */
const DEFAULT_BOT: Omit<Bot, 'id'> = {
  name: '美妆销售顾问',
  project: 'GlowLab',
  workflow: '销售接待主流程',
  status: 'online',
  tone: '亲切专业',
  score: 92,
  desc: '为消费者提供亲切、专业的美妆销售接待与咨询服务。',
}

const TABS = [
  { id: 'training', label: '训练调整', icon: MessageSquare },
  { id: 'orchestrate', label: '编排', icon: GitBranch },
]

/**
 * 机器人详情页（/bots/:botId）。
 * mock-first：按 id 从 MOCK_BOTS 同步取数，无异步 / 无 loading。
 */
export default function BotDetailPage() {
  const { botId } = useParams<{ botId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('training')

  const base = (botId ? MOCK_BOTS[botId] : undefined) ?? DEFAULT_BOT
  const bot: Bot = { id: botId ?? 'unknown', ...base }
  const botRef: BotRef = { id: bot.id, name: bot.name }

  return (
    <div className="bot-detail-page">
      <div className="detail-header">
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
                {bot.status === 'online' ? '已上线' : '训练中'}
              </span>
            </div>
          </div>
        </div>

        <div className="detail-actions">
          <Button variant="secondary" size="sm" onClick={() => toast('演示环境：数据看板未接入')}>
            查看数据
          </Button>
          <Button variant="primary" size="sm" onClick={() => toast('已发布上线')}>
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
              onClick={() => {
            if (tab.id === 'orchestrate') {
              navigate(`/bots/${botId}/orchestrate`)
            } else {
              setActiveTab(tab.id)
            }
          }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      <div className="detail-content">
        {activeTab === 'training' && <TrainingTab bot={botRef} />}
      </div>
    </div>
  )
}
