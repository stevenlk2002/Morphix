/** 搜索添加外部联系人（P1-2）：按手机号/关键词搜索 → 发送好友申请 → 落库联系人。 */

import { useState } from 'react'
import Modal from '../../../components/common/Modal'
import Button from '../../../components/common/Button'
import { channelsApi } from '../../../api/client'
import type { ContactSearchResultDTO } from '../../../types/channels'
import { toast, errText } from '../../../utils/toast'

interface Props {
  open: boolean
  /** 关联渠道账号 id（用于搜索/添加后端反查 uuid）。 */
  accountId: string
  onClose: () => void
  onAdded?: () => void
}

export default function SearchAddContactModal({ open, accountId, onClose, onAdded }: Props) {
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<ContactSearchResultDTO[]>([])
  const [adding, setAdding] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!keyword.trim()) {
      toast('请输入手机号或关键词')
      return
    }
    if (!accountId) {
      toast('未关联渠道账号，无法搜索')
      return
    }
    setLoading(true)
    try {
      const list = await channelsApi.searchContact(accountId, keyword.trim())
      setResults(list)
      if (list.length === 0) toast('未搜索到匹配的联系人')
    } catch (e) {
      toast(`搜索失败：${errText(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async (item: ContactSearchResultDTO) => {
    setAdding(item.userId)
    try {
      await channelsApi.addSearchContact(accountId, {
        vid: item.userId,
        openId: item.openId,
        phone: '',
        content: '您好，我是您的专属顾问，期待为您服务',
        ticket: item.ticket,
      })
      toast(`已向「${item.name || item.userId}」发送好友申请`)
      onAdded?.()
    } catch (e) {
      toast(`添加失败：${errText(e)}`)
    } finally {
      setAdding(null)
    }
  }

  return (
    <Modal
      open={open}
      title="搜索添加外部联系人"
      onClose={onClose}
      width={520}
      footer={<Button variant="secondary" size="sm" onClick={onClose}>关闭</Button>}
    >
      <div className="form-group">
        <label className="form-label">手机号 / 关键词</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input"
            placeholder="请输入手机号或关键词"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch()
            }}
            style={{ flex: 1 }}
          />
          <Button variant="primary" size="sm" disabled={loading} onClick={handleSearch}>
            搜索
          </Button>
        </div>
      </div>

      <div className="search-add-results">
        {loading && (
          <div className="detail-empty" style={{ padding: 24 }}>搜索中…</div>
        )}
        {!loading && results.length === 0 && (
          <div className="detail-empty" style={{ padding: 24, color: 'var(--text-tertiary)', fontSize: 13 }}>
            输入手机号或关键词后点击「搜索」
          </div>
        )}
        {!loading &&
          results.map((r) => (
            <div className="search-add-item" key={r.userId}>
              <div className="search-add-avatar">
                {r.headImg ? (
                  <img src={r.headImg} alt="" />
                ) : (
                  (r.name || r.userId || '?').slice(0, 1)
                )}
              </div>
              <div className="search-add-info">
                <div className="search-add-name">{r.name || '未知'}</div>
                <div className="search-add-sub">{r.userId}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={adding === r.userId}
                onClick={() => handleAdd(r)}
              >
                {adding === r.userId ? '发送中' : '添加'}
              </Button>
            </div>
          ))}
      </div>
    </Modal>
  )
}
