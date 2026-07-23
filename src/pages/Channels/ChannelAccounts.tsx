/** 渠道账号管理（ACC）：团队信息条 + 账号卡片网格 + 添加入口。 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Settings, Link2, Users } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import type {
  AccountDTO,
  AvailableBotDTO,
  SetDefaultBotsRequest,
  TeamDTO,
} from '../../types/channels'
import TeamSelector from './shared/TeamSelector'
import ChannelTypeBadge from './shared/ChannelTypeBadge'
import WecomNameIcon from './shared/WecomNameIcon'
import AccountSettingsModal from './shared/AccountSettingsModal'
import { avatarColor, avatarChar } from './shared/avatar'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

/** 在线徽标文案。 */
function onlineBadge(status: string, protocol: string): { text: string; offline: boolean } {
  if (status !== 'online') return { text: '离线', offline: true }
  return { text: protocol ? 'ipad在线' : '在线', offline: false }
}

/** 圆形真实头像：有图用 <img>，加载失败回退首字母 + 底色。 */
function AccountAvatar({ account }: { account: AccountDTO }) {
  const [imgFailed, setImgFailed] = useState(false)
  if (account.avatar && !imgFailed) {
    return (
      <img
        className="channel-account-avatar-img"
        src={account.avatar}
        alt={account.name}
        onError={() => setImgFailed(true)}
      />
    )
  }
  return <span className="channel-account-avatar-initial">{avatarChar(account.name)}</span>
}

export default function ChannelAccountsPage() {
  const navigate = useNavigate()
  const [teams, setTeams] = useState<TeamDTO[]>([])
  const [accounts, setAccounts] = useState<AccountDTO[]>([])
  const [availableBots, setAvailableBots] = useState<AvailableBotDTO[]>([])
  const [loading, setLoading] = useState(true)
  // 当前选中团队 id（P0 仅 UI 切换，不做账号列表数据联动）
  const [currentTeamId, setCurrentTeamId] = useState<string>('')
  // 设置弹层状态（整层：默认机器人配置 + 上下线切换）
  const [modal, setModal] = useState<{ accountId: string } | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([
      channelsApi.listTeams(),
      channelsApi.listAccounts(),
      channelsApi.listAvailableBots(),
    ])
      .then(([t, a, bots]) => {
        if (!alive) return
        setTeams(t)
        setAccounts(a)
        setAvailableBots(bots)
        setCurrentTeamId(t[0]?.id ?? '')
      })
      .catch((e) => toast(`加载失败：${errText(e)}`))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  const modalAccount = modal ? accounts.find((a) => a.id === modal.accountId) : undefined

  /** 「设置」弹层内保存默认机器人。 */
  const handleSaveSettings = async (payload: SetDefaultBotsRequest) => {
    if (!modalAccount) return
    const accountId = modalAccount.id
    try {
      const updated = await channelsApi.setDefaultBots(accountId, payload)
      setAccounts((prev) =>
        prev.map((a) => (a.id === accountId ? { ...a, ...updated } : a))
      )
      toast('已更新默认机器人')
      setModal(null)
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    }
  }

  /** 「设置」弹层内切换上下线（立即生效，不关闭弹层）。 */
  const handleStatusChange = async (status: 'online' | 'offline') => {
    if (!modalAccount) return
    const accountId = modalAccount.id
    try {
      const updated = await channelsApi.updateAccountStatus(accountId, { status })
      setAccounts((prev) =>
        prev.map((a) => (a.id === accountId ? { ...a, ...updated } : a))
      )
      toast(status === 'offline' ? '账号已下线' : '账号已上线')
    } catch (e) {
      toast(`操作失败：${errText(e)}`)
    }
  }

  return (
    <div className="channel-accounts-page">
      <div className="filter-bar channel-accounts-header">
        <TeamSelector
          teams={teams}
          currentTeamId={currentTeamId}
          onSelect={(teamId) => setCurrentTeamId(teamId)}
        />
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
                {/* 顶部：圆形头像 + 名称 + 企微图标 + 在线徽标 */}
                <div className="channel-account-top">
                  <div
                    className="channel-account-avatar"
                    style={{ background: avatarColor(a.id) }}
                  >
                    <AccountAvatar account={a} />
                    <ChannelTypeBadge channelType={a.channelType} />
                  </div>
                  <div className="channel-account-head">
                    <div className="channel-account-name">
                      <span className="channel-account-name-text">{a.name}</span>
                      <WecomNameIcon size={14} />
                      <span
                        className={`channel-online-badge${badge.offline ? ' offline' : ' ipad'}`}
                      >
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

                {/* 账号会话数 */}
                <div className="channel-account-sessions">
                  账号会话 <b>{a.sessionsCount}</b>
                </div>

                {/* 底部横排操作 */}
                <div className="channel-account-actions">
                  <Button
                    variant="outline"
                    size="sm"
                    icon={<Settings size={14} />}
                    onClick={() => setModal({ accountId: a.id })}
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

      {/* 设置弹层（默认机器人 + 上下线切换） */}
      {modal && modalAccount && (
        <AccountSettingsModal
          open={!!modal}
          account={modalAccount}
          bots={availableBots}
          onClose={() => setModal(null)}
          onSave={handleSaveSettings}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  )
}
