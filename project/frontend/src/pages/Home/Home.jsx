import { useEffect, useState } from 'react'
import { Activity, Bot, MessageCircle, Users, TrendingUp } from 'lucide-react'
import { dashboardApi } from '../../utils/api'
import './Home.css'

export default function HomePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboard()
  }, [])

  const loadDashboard = async () => {
    try {
      const result = await dashboardApi.get()
      setData(result)
    } catch (error) {
      console.error('加载仪表板失败:', error)
    } finally {
      setLoading(false)
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

  const stats = data?.stats || {}

  return (
    <div className="home-page">
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
            <Bot size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-label">活跃项目</div>
            <div className="stat-value">{stats.activeProjects}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
            <MessageCircle size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-label">托管账号</div>
            <div className="stat-value">{stats.channelAccounts}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--info-bg)', color: 'var(--info)' }}>
            <Users size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-label">AI 会话</div>
            <div className="stat-value">{stats.aiSessions}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>
            <TrendingUp size={20} />
          </div>
          <div className="stat-content">
            <div className="stat-label">转化率</div>
            <div className="stat-value">{stats.conversionRate}</div>
          </div>
        </div>
      </div>

      <div className="dashboard-row">
        <div className="dashboard-section">
          <h3 className="section-title">最近会话</h3>
          <div className="session-list">
            {data?.sessions?.map((session) => (
              <div key={session.id} className="session-item">
                <div className="session-info">
                  <div className="session-name">{session.name}</div>
                  <div className="session-meta">
                    <span className="session-channel">{session.channel}</span>
                    <span className="session-dot">·</span>
                    <span className="session-bot">{session.bot}</span>
                  </div>
                </div>
                <div className="session-right">
                  <span className={`session-state state-${session.state === 'AI托管' ? 'ai' : 'human'}`}>
                    {session.state}
                  </span>
                  <span className="session-time">{session.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="dashboard-section">
          <h3 className="section-title">机器人状态</h3>
          <div className="bot-list">
            {data?.bots?.slice(0, 5).map((bot) => (
              <div key={bot.id} className="bot-item">
                <div className="bot-item-avatar">
                  <Bot size={16} />
                </div>
                <div className="bot-item-info">
                  <div className="bot-item-name">{bot.name}</div>
                  <div className="bot-item-project">{bot.project}</div>
                </div>
                <span className={`bot-item-status status-${bot.status}`}>
                  {bot.status === 'online' ? '在线' : '训练中'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
