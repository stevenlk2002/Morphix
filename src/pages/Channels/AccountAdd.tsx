/** 添加渠道账号（AccountAdd）：步骤条 + 渠道类型选择 + 扫码占位。 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, QrCode } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './Channels.css'

type ChannelKey = 'wecom' | 'wechat' | 'whatsapp'

interface ChannelMeta {
  key: ChannelKey
  icon: string
  label: string
  protocol?: string
}

const CHANNELS: ChannelMeta[] = [
  { key: 'wecom', icon: '企', label: '企业微信', protocol: 'ipad' },
  { key: 'wechat', icon: '微', label: '微信', protocol: 'ipad' },
  { key: 'whatsapp', icon: 'W', label: 'WhatsApp' },
]

export default function AccountAddPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<1 | 2>(1)
  const [selected, setSelected] = useState<ChannelKey | null>(null)
  const [teamId, setTeamId] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    channelsApi
      .listTeams()
      .then((t) => setTeamId(t[0]?.id ?? 'team-initial'))
      .catch(() => setTeamId('team-initial'))
  }, [])

  const selectedMeta = CHANNELS.find((c) => c.key === selected)

  const handleCreate = async () => {
    if (!selectedMeta) return
    setSubmitting(true)
    try {
      const name = `${selectedMeta.label}-${new Date().toISOString().slice(11, 16).replace(':', '')}`
      await channelsApi.createAccount({
        channelType: selectedMeta.key,
        protocol: selectedMeta.protocol,
        teamId,
        name,
      })
      toast('渠道账号已创建（演示：扫码接入为占位流程）')
      navigate('/channels/accounts')
    } catch (e) {
      toast(`创建失败：${errText(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="channel-accounts-page">
      <div className="stepper">
        <div className={`step ${step === 1 ? 'active' : 'done'}`}>
          <div className="step-num">{step > 1 ? '✓' : 1}</div>
          选择渠道类型
        </div>
        <div className="step-line" />
        <div className={`step ${step === 2 ? 'active' : ''}`}>
          <div className="step-num">2</div>
          添加渠道账号
        </div>
      </div>

      {step === 1 ? (
        <div className="card">
          <div className="card-head">
            <h3>选择渠道类型</h3>
          </div>
          <div className="form-group">
            <label className="form-label">渠道类型</label>
            <div className="channel-type-grid">
              {CHANNELS.map((c) => (
                <div
                  key={c.key}
                  className={`channel-type-card ${c.key}${selected === c.key ? ' selected' : ''}`}
                  onClick={() => setSelected(c.key)}
                >
                  <div className="channel-type-icon">{c.icon}</div>
                  <div style={{ fontSize: 13 }}>{c.label}</div>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
            <Button variant="secondary" onClick={() => navigate('/channels/accounts')}>
              取消
            </Button>
            <Button icon={<ChevronRight size={16} />} disabled={!selected} onClick={() => setStep(2)}>
              下一步
            </Button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ maxWidth: 440, margin: '0 auto', textAlign: 'center', padding: 40 }}>
          <div style={{ marginBottom: 16 }}>请使用{selectedMeta?.label}扫码添加</div>
          <div
            style={{
              width: 200,
              height: 200,
              margin: '0 auto',
              borderRadius: 16,
              display: 'grid',
              placeItems: 'center',
              background: 'var(--surface-soft)',
              border: '1px solid var(--line)',
              color: 'var(--muted)',
            }}
          >
            <QrCode size={120} strokeWidth={1} />
          </div>
          <div style={{ marginTop: 16, fontSize: 12, color: 'var(--muted)' }}>扫码添加渠道账号</div>
          <div style={{ marginTop: 24, display: 'flex', gap: 10, justifyContent: 'center' }}>
            <Button variant="secondary" onClick={() => setStep(1)}>
              上一步
            </Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting ? '提交中…' : '确认添加'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
