/** 渠道账号管理（ACC）：团队信息条 + 账号卡片网格 + 添加入口。 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Settings, Link2, Users } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import type { AccountDTO, TeamDTO } from '../../types/channels'
import TeamInfoBar from './shared/TeamInfoBar'
import ChannelTypeBadge from './shared/ChannelTypeBadge'
import { avatarColor } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

/** 在线徽标文案。 */
function onlineBadge(status: string, protocol: string): { text: string; offline: boolean } {
  if (status !== 'online') return { text: '离线', offline: true }
  return { text: protocol ? 'ipad在线' : '在线', offline: false }
}

export default function ChannelAccountsPage() {
  const navigate = useNavigate()
  const [teams, setTeams] = useState<TeamDTO[]>([])
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.all([channelsApi.listTeams(), channelsApi.listAccounts()])
      .then(([t, a]) => {
        if (!alive) return
        setTeams(t)
        setAccounts(a)
      })
      .catch((e) => toast(`加载失败：${errText(e)}`))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  const currentTeam = teams[0]

  return (
    <div className="channel-accounts-page">
      <div className="filter-bar channel-accounts-header">
        {currentTeam ? (
          <TeamInfoBar
            name={currentTeam.name}
            seatsLeft={currentTeam.seatsLeft}
            energyValue={currentTeam.energyValue}
          />
        ) : (
          <div className="channel-team-info">
            <span className="channel-team-name">初始团队</span>
          </div>
        )}
        <div className="channel-header-actions">
          <Button icon={<Plus size={16} />} onClick={() => navigate('/channels/accounts/add')}>
            添加渠道账号
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="placeholder">
          <h3>加载中…</h3>
        </div>
      ) : (
        <div className="channel-cards-grid">
          <div
            className="channel-add-card"
            onClick={() => navigate('/channels/accounts/add')}
          >
            <div className="channel-add-icon">
              <Plus size={24} />
            </div>
            <div className="channel-add-title">添加渠道账号</div>
            <div className="channel-add-desc">支持企业微信、WhatsApp、企业WhatsApp</div>
          </div>

          {accounts.map((a) => {
            const badge = onlineBadge(a.status, a.protocol)
            return (
              <div className="channel-account-card" key={a.id}>
                <div className="channel-account-main">
                  <div className="channel-account-avatar" style={{ background: avatarColor(a.id) }}>
                    {a.name.charAt(0)}
                    <ChannelTypeBadge channelType={a.channelType} />
                  </div>
                  <div className="channel-account-info">
                    <div className="channel-account-name">
                      <span>{a.name}</span>
                      <span className={`channel-online-badge${badge.offline ? ' offline' : ' ipad'}`}>
                        {!badge.offline && (
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        )}
                        {badge.text}
                      </span>
                    </div>
                    <div className="channel-account-protocol">
                      {a.channel} · {a.protocol ? `${a.protocol}协议` : '未配置协议'}
                    </div>
                  </div>
                </div>
                <div className="channel-account-stats">
                  <div className="channel-stat-label">账号会话</div>
                  <div className="channel-stat-value">{a.sessionsCount}</div>
                </div>
                <div className="channel-account-actions">
                  <Button
                    variant="outline"
                    size="sm"
                    icon={<Settings size={14} />}
                    onClick={() => navigate(`/channels/accounts/${a.id}/hosting`)}
                  >
                    设置
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={<Users size={14} />}
                    onClick={() => navigate(`/channels/accounts/${a.id}/hosting`)}
                  >
                    托管管理
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={<Link2 size={14} />}
                    onClick={() => toast('换绑团队（P2 暂未开放）')}
                  >
                    换绑团队
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
