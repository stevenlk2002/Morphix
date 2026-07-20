import { useState, useEffect, useMemo } from 'react'
import { operationsTasksApi } from '../../../api/operations'
import type { ChannelAccount } from '../../../types/operations'

/** MomentsChannel → 后端 channel_type 映射。 */
const CHANNEL_MAP: Record<string, string> = {
  '微信': 'wechat',
  '企业微信': 'wecom',
  'WhatsApp': 'whatsapp',
}

interface Props {
  /** 朋友圈渠道（前端值：微信 / 企业微信 / WhatsApp）。 */
  channel: string
  /** 已选账号 ID 列表。 */
  selectedIds: string[]
  /** 选择变更回调。 */
  onChange: (ids: string[]) => void
}

/** 朋友圈任务 Step 3：按渠道账号选择运营对象。 */
export default function AccountSelector({ channel, selectedIds, onChange }: Props) {
  const [accounts, setAccounts] = useState<ChannelAccount[]>([])
  const [loading, setLoading] = useState(false)

  const backendChannel = CHANNEL_MAP[channel] || ''

  useEffect(() => {
    if (!backendChannel) {
      setAccounts([])
      return
    }
    setLoading(true)
    operationsTasksApi
      .listChannelAccounts(backendChannel)
      .then((data) => setAccounts(data))
      .catch(() => setAccounts([]))
      .finally(() => setLoading(false))
  }, [backendChannel])

  /** 将 string[] 转为 Set 以便 O(1) 查找。 */
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  /** 在线账号列表。 */
  const onlineAccounts = useMemo(
    () => accounts.filter((a) => a.status === 'online'),
    [accounts],
  )

  /** 当前页是否全选（仅在线账号）。 */
  const allOnlineChecked =
    onlineAccounts.length > 0 && onlineAccounts.every((a) => selectedSet.has(a.id))
  const someOnlineChecked = onlineAccounts.some((a) => selectedSet.has(a.id))
  const indeterminate = someOnlineChecked && !allOnlineChecked

  const toggleAllOnline = () => {
    const next = new Set(selectedSet)
    if (allOnlineChecked) {
      onlineAccounts.forEach((a) => next.delete(a.id))
    } else {
      onlineAccounts.forEach((a) => next.add(a.id))
    }
    onChange(Array.from(next))
  }

  const toggleOne = (id: string) => {
    const next = new Set(selectedSet)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(Array.from(next))
  }

  return (
    <div className="target-panel">
      {/* 已选计数 */}
      <div className="target-select-row" style={{ marginBottom: 0 }}>
        <span className="target-selected-count">
          已选中 <strong>{selectedSet.size}</strong> 个账号
        </span>
      </div>

      {/* 表格 */}
      <div className="target-table-wrapper">
        {loading ? (
          <div className="target-loading">加载中...</div>
        ) : (
          <table className="proto-table target-data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={allOnlineChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = indeterminate
                    }}
                    onChange={toggleAllOnline}
                    disabled={onlineAccounts.length === 0}
                  />
                </th>
                <th>账号名称</th>
                <th>渠道类型</th>
                <th style={{ width: 80, textAlign: 'center' }}>在线状态</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {accounts.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: 24 }}>
                    该渠道暂无可用账号
                  </td>
                </tr>
              ) : (
                accounts.map((account) => {
                  const isOnline = account.status === 'online'
                  const isChecked = selectedSet.has(account.id)
                  return (
                    <tr
                      key={account.id}
                      className={isChecked ? 'target-row-selected' : ''}
                      style={isOnline ? {} : { color: 'var(--text-tertiary)' }}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          disabled={!isOnline}
                          title={isOnline ? undefined : '该账号离线，无法发送朋友圈'}
                          onChange={() => toggleOne(account.id)}
                        />
                      </td>
                      <td>{account.account_name}</td>
                      <td>
                        <span className={`proto-badge ${
                          account.channel_type === 'wecom' ? 'proto-badge-info' :
                          account.channel_type === 'wechat' ? 'proto-badge-success' :
                          'proto-badge-neutral'
                        }`}>
                          {account.channel_type === 'wecom' ? '企业微信' :
                           account.channel_type === 'wechat' ? '微信' :
                           account.channel_type}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 10,
                            height: 10,
                            borderRadius: '50%',
                            backgroundColor: isOnline ? '#22c55e' : '#9ca3af',
                          }}
                          title={isOnline ? '在线' : '离线'}
                        />
                      </td>
                      <td className="text-secondary">{isOnline ? '—' : '离线'}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
