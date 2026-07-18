import { useState } from 'react'
import { MessageSquare, Power } from 'lucide-react'
import Button from '../../components/common/Button'
import '../../pages/prototype.css'

interface HostedSession {
  id: string
  customer: string
  channel: string
  bot: string
  hosted: boolean
  lastMessage: string
}

const MOCK: HostedSession[] = [
  { id: 's-1', customer: '张敏', channel: '企业微信', bot: '美妆销售顾问', hosted: true, lastMessage: '这款面霜适合敏感肌吗？' },
  { id: 's-2', customer: '李雷', channel: '个人微信', bot: '护肤推荐官', hosted: true, lastMessage: '有没有优惠活动？' },
  { id: 's-3', customer: '王芳', channel: 'WhatsApp', bot: 'Overseas Helper', hosted: false, lastMessage: 'Can you ship to SG?' },
  { id: 's-4', customer: '陈静', channel: '企业微信', bot: '美妆销售顾问', hosted: true, lastMessage: '我已经下单啦' },
]

export default function ChannelSessionsPage() {
  const [sessions, setSessions] = useState<HostedSession[]>(MOCK)

  const toggle = (id: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, hosted: !s.hosted } : s))
    )
  }

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">渠道会话托管</h2>
          <p className="page-subtitle">开启 / 关闭机器人托管，进入会话查看运行轨迹</p>
        </div>
      </div>

      <div className="proto-card">
        <table className="proto-table">
          <thead>
            <tr>
              <th>客户</th>
              <th>渠道</th>
              <th>当前机器人</th>
              <th>最近消息</th>
              <th>托管</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>{s.customer}</td>
                <td>{s.channel}</td>
                <td>{s.bot}</td>
                <td className="text-secondary">{s.lastMessage}</td>
                <td>
                  <span className={`proto-badge ${s.hosted ? 'proto-badge-success' : 'proto-badge-neutral'}`}>
                    {s.hosted ? '托管中' : '已关闭'}
                  </span>
                </td>
                <td>
                  <div className="proto-actions">
                    <Button variant="ghost" size="sm" icon={<MessageSquare size={14} />}>
                      进入会话
                    </Button>
                    <Button
                      variant={s.hosted ? 'ghost' : 'primary'}
                      size="sm"
                      icon={<Power size={14} />}
                      onClick={() => toggle(s.id)}
                    >
                      {s.hosted ? '关闭托管' : '开启托管'}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
