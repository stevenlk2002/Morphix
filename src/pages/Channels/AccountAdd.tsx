/** 添加渠道账号（AccountAdd）：6 步向导容器（type → protocol → qr → waiting → verify → done）。 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, MessageCircle, MessageSquare } from 'lucide-react'
import { channelsApi } from '../../api/client'
import { toast } from '../../utils/toast'
import { useWecomHosting } from './useWecomHosting'
import {
  StepType,
  StepProtocol,
  StepQr,
  StepVerify,
  StepDone,
  type ChannelMeta,
} from './ChannelAddSteps'
import '../../pages/prototype.css'
import './Channels.css'
import './ChannelAdd.css'

const CHANNELS: ChannelMeta[] = [
  {
    key: 'wecom',
    Icon: Building2,
    label: '企业微信',
    desc: '企业内部沟通协作平台',
    iconBg: 'var(--primary-light)',
    iconColor: 'var(--primary)',
  },
  {
    key: 'wechat',
    Icon: MessageCircle,
    label: '微信',
    desc: '个人微信账号接入',
    iconBg: 'var(--green-soft)',
    iconColor: 'var(--green)',
  },
  {
    key: 'whatsapp',
    Icon: MessageSquare,
    label: 'WhatsApp',
    desc: '海外客户沟通渠道',
    iconBg: 'var(--green-soft)',
    iconColor: 'var(--green)',
  },
]

export default function AccountAddPage() {
  const navigate = useNavigate()
  const [teamId, setTeamId] = useState('')
  const [seatsLeft, setSeatsLeft] = useState<number | null>(null)

  const {
    step,
    setStep,
    selectedChannel,
    setSelectedChannel,
    selectedProtocol,
    setSelectedProtocol,
    startData,
    userInfo,
    verifyError,
    submitting,
    qrCountdown,
    expired,
    beginScan,
    submitCode,
    goToVerify,
    refresh,
  } = useWecomHosting()

  useEffect(() => {
    channelsApi
      .listTeams()
      .then((teams) => {
        const t = teams[0]
        setTeamId(t?.id ?? 'team-initial')
        setSeatsLeft(t?.seatsLeft ?? null)
      })
      .catch(() => {
        setTeamId('team-initial')
        setSeatsLeft(null)
      })
  }, [])

  const handleSelectChannel = (key: ChannelMeta['key']) => {
    if (key === 'wecom') {
      setSelectedChannel('wecom')
    } else {
      toast('该渠道暂未接入真实协议，本期仅企业微信可用')
      setSelectedChannel(null)
    }
  }

  const handleCreate = () => {
    if (!teamId) return
    void beginScan(teamId, 'wecom', selectedProtocol)
  }

  const renderStep = () => {
    switch (step) {
      case 'type':
        return (
          <StepType
            channels={CHANNELS}
            selected={selectedChannel}
            seatsLeft={seatsLeft}
            onSelect={handleSelectChannel}
            onNext={() => setStep('protocol')}
            onCancel={() => navigate('/channels/accounts')}
          />
        )
      case 'protocol':
        return (
          <StepProtocol
            protocol={selectedProtocol}
            onChange={setSelectedProtocol}
            onBack={() => setStep('type')}
            onCreate={handleCreate}
            submitting={submitting}
          />
        )
      case 'qr':
        return startData ? (
          <StepQr
            startData={startData}
            countdown={qrCountdown}
            expired={expired}
            onBack={() => setStep('protocol')}
            onRefresh={refresh}
            onNext={goToVerify}
          />
        ) : null
      case 'verify':
        return (
          <StepVerify
            userInfo={userInfo}
            verifyError={verifyError}
            submitting={submitting}
            onBack={() => setStep('qr')}
            onRescan={refresh}
            onSubmit={(code) => void submitCode(code)}
          />
        )
      case 'done':
        return <StepDone />
      default:
        return null
    }
  }

  return (
    <div className="channel-accounts-page">
      <div className="stepper">
        <div className={`step ${step === 'type' ? 'active' : 'done'}`}>
          <div className="step-num">{step === 'type' ? 1 : '✓'}</div>
          选择渠道类型
        </div>
        <div className="step-line" />
        <div className={`step ${step !== 'type' ? 'active' : ''}`}>
          <div className="step-num">2</div>
          添加渠道账号
        </div>
      </div>
      {renderStep()}
    </div>
  )
}
