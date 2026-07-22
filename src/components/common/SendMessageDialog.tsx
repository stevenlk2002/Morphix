/** 发送消息对话框（复用 iPad 协议发送能力）。

复用于：联系人详情「发消息」、客户详情「发消息」、群详情「发消息」。
根据传入的 targetType/targetId 由后端反查 user_id/room_id 并发送。
*/
import { useState } from 'react'
import Modal from './Modal'
import Button from './Button'
import { channelsApi } from '../../api/client'
import { toast, errText } from '../../utils/toast'

interface Props {
  open: boolean
  /** 标题（如「发消息给 张三」）。 */
  title: string
  accountId: string
  /** contact | room | session */
  targetType: 'contact' | 'room' | 'session'
  targetId: string
  onClose: () => void
  onSent?: (result: { msgId: string }) => void
}

export default function SendMessageDialog({
  open,
  title,
  accountId,
  targetType,
  targetId,
  onClose,
  onSent,
}: Props) {
  const [content, setContent] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSend = async () => {
    if (!content.trim()) {
      toast('请输入消息内容')
      return
    }
    if (!accountId) {
      toast('该联系人未关联渠道账号，无法发送')
      return
    }
    setBusy(true)
    try {
      const res = await channelsApi.sendTextMessage(accountId, targetType, targetId, content.trim())
      toast('消息已发送')
      onSent?.(res)
      setContent('')
      onClose()
    } catch (e) {
      toast(`发送失败：${errText(e)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" size="sm" disabled={busy} onClick={handleSend}>
            发送
          </Button>
        </>
      }
    >
      <div className="form-group">
        <textarea
          className="input"
          rows={4}
          placeholder="请输入要发送的文本消息"
          maxLength={2000}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={{ width: '100%' }}
        />
        <div className="customer-char-count">{content.length}/2000</div>
      </div>
    </Modal>
  )
}
