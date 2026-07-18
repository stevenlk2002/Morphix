import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Sparkles, Activity } from 'lucide-react'
import Button from '../../components/common/Button'
import { botsApi } from '../../utils/api'
import './Bots.css'

export default function BotsPage() {
  const navigate = useNavigate()
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadBots()
  }, [])

  const loadBots = async () => {
    try {
      const data = await botsApi.list()
      setBots(data)
    } catch (error) {
      console.error('加载机器人失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTrain = async (botId) => {
    try {
      await botsApi.train(botId)
      loadBots()
    } catch (error) {
      console.error('训练失败:', error)
    }
  }

  if (loading) {
    return (
      <div className="page-loading">
        <Activity className="spinner" size={32} />
        <p>加载中...</p>
      </div>
    )
  }

  return (
    <div className="bots-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">AI 机器人</h2>
          <p className="page-subtitle">管理和训练您的 AI 销售助手</p>
        </div>
        <Button icon={<Plus size={16} />}>创建机器人</Button>
      </div>

      <div className="bots-grid">
        {bots.map((bot) => (
          <div key={bot.id} className="bot-card">
            <div className="bot-card-header">
              <div className="bot-avatar">
                <Sparkles size={20} />
              </div>
              <div className="bot-info">
                <h3 className="bot-name">{bot.name}</h3>
                <p className="bot-project">{bot.project}</p>
              </div>
              <span className={`bot-status status-${bot.status}`}>
                {bot.status === 'online' ? '在线' : '训练中'}
              </span>
            </div>

            <div className="bot-card-body">
              <div className="bot-meta">
                <div className="bot-meta-item">
                  <span className="bot-meta-label">工作流</span>
                  <span className="bot-meta-value">{bot.workflow}</span>
                </div>
                <div className="bot-meta-item">
                  <span className="bot-meta-label">风格</span>
                  <span className="bot-meta-value">{bot.tone}</span>
                </div>
              </div>

              <div className="bot-score">
                <div className="bot-score-bar">
                  <div
                    className="bot-score-fill"
                    style={{ width: `${bot.score}%` }}
                  />
                </div>
                <span className="bot-score-text">训练度 {bot.score}%</span>
              </div>
            </div>

            <div className="bot-card-footer">
              <Button variant="ghost" size="sm" onClick={() => navigate(`/bots/${bot.id}`)}>
                查看详情
              </Button>
              {bot.status === 'training' && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleTrain(bot.id)}
                >
                  继续训练
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
