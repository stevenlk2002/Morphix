/**
 * ChannelAddSteps —— 添加渠道账号向导各步骤的纯展示组件。
 * 无业务副作用：仅渲染 UI，状态与回调全部由 AccountAdd 容器（useWecomHosting）透传。
 */

import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ClipboardEvent } from 'react'
import { ChevronRight, CheckCircle2, Tablet, type LucideIcon } from 'lucide-react'
import Button from '../../components/common/Button'
import type { ChannelKey, ProtocolKey, WecomStartData } from './useWecomHosting'
import type { WecomUserInfo } from '../../types/channels'

/** 渠道元数据（图标 + 展示文案 + 配色）。 */
export interface ChannelMeta {
  key: ChannelKey
  Icon: LucideIcon
  label: string
  desc: string
  iconBg: string
  iconColor: string
}

/* ============================ type ============================ */
interface StepTypeProps {
  channels: ChannelMeta[]
  selected: ChannelKey | null
  seatsLeft: number | null
  onSelect: (key: ChannelKey) => void
  onNext: () => void
  onCancel: () => void
}

export function StepType({ channels, selected, seatsLeft, onSelect, onNext, onCancel }: StepTypeProps) {
  return (
    <div className="card" style={{ maxWidth: 520, margin: '0 auto', padding: 0 }}>
      <div className="card-body" style={{ padding: '28px 24px' }}>
        <div className="form-group">
          <label className="form-label" style={{ fontWeight: 600, fontSize: 14 }}>
            添加渠道账号
          </label>
          {seatsLeft !== null && (
            <div className="channel-add-seats">
              <span className="channel-add-seats-text">
                剩余席位 <em>{seatsLeft}个</em>
              </span>
              <span className="channel-add-seats-buy">购买更多</span>
            </div>
          )}
          <div className="channel-type-list">
            {channels.map((c) => (
              <div
                key={c.key}
                className={`channel-type-card${c.key === selected ? ' selected' : ''}`}
                onClick={() => onSelect(c.key)}
              >
                <div className="channel-type-icon" style={{ background: c.iconBg, color: c.iconColor }}>
                  <c.Icon size={20} />
                </div>
                <div className="channel-type-info">
                  <div className="channel-type-name">{c.label}</div>
                  <div className="channel-type-desc">{c.desc}</div>
                </div>
                <span className="channel-type-arrow">
                  <ChevronRight size={16} />
                </span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <Button variant="secondary" onClick={onCancel}>
            取消
          </Button>
          <Button variant="primary" disabled={selected !== 'wecom'} onClick={onNext}>
            下一步
          </Button>
        </div>
      </div>
    </div>
  )
}

/* ============================ protocol ============================ */
interface StepProtocolProps {
  protocol: ProtocolKey
  onChange: (p: ProtocolKey) => void
  onBack: () => void
  onCreate: () => void
  submitting: boolean
}

const PROTOCOL_OPTIONS: { value: ProtocolKey; name: string; hint: string }[] = [
  { value: 'ipod', name: 'IPad (推荐)', hint: 'iPad 协议 · 稳定 · 风险低' },
  { value: 'pc', name: 'pc', hint: 'PC 协议 · 兼容老系统' },
]

export function StepProtocol({ protocol, onChange, onBack, onCreate, submitting }: StepProtocolProps) {
  const [open, setOpen] = useState(false)
  const selectRef = useRef<HTMLDivElement | null>(null)
  const current = PROTOCOL_OPTIONS.find((o) => o.value === protocol) ?? PROTOCOL_OPTIONS[0]

  useEffect(() => {
    if (!open) return
    const onDoc = (e: globalThis.MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <div className="card" style={{ maxWidth: 480, margin: '0 auto', padding: 0 }}>
      <div className="card-body" style={{ padding: '28px 24px' }}>
        <div className="form-group">
          <label className="form-label" style={{ fontWeight: 600, fontSize: 14 }}>
            协议选择 <span style={{ color: 'var(--error)' }}>*</span>
          </label>
          <div className="channel-protocol-select" ref={selectRef}>
            <div className="channel-protocol-trigger" onClick={() => setOpen((v) => !v)}>
              <span className="channel-protocol-icon">
                <Tablet size={16} />
              </span>
              <span className="channel-protocol-value">{current.name}</span>
              <span className="channel-protocol-caret">
                <ChevronRight size={16} style={{ transform: 'rotate(90deg)' }} />
              </span>
            </div>
            {open && (
              <div className="channel-protocol-dropdown">
                {PROTOCOL_OPTIONS.map((o) => (
                  <div
                    key={o.value}
                    className={`channel-protocol-option${o.value === protocol ? ' selected' : ''}`}
                    onClick={() => {
                      onChange(o.value)
                      setOpen(false)
                    }}
                  >
                    <span className="channel-protocol-radio" />
                    <span className="channel-protocol-text">
                      <span className="channel-protocol-name">{o.name}</span>
                      <span className="channel-protocol-hint">{o.hint}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="channel-protocol-tip">基于 iPad 协议登录，账号更稳定，掉线率低</div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <Button variant="secondary" onClick={onBack}>
            上一步
          </Button>
          <Button variant="primary" onClick={onCreate} disabled={submitting}>
            {submitting ? '创建中…' : '创建账号'}
          </Button>
        </div>
      </div>
    </div>
  )
}

/* ============================ qr ============================ */
interface StepQrProps {
  startData: WecomStartData
  countdown: number
  expired: boolean
  onBack: () => void
  onRefresh: () => void
  onNext: () => void
}

export function StepQr({ startData, countdown, expired, onBack, onRefresh, onNext }: StepQrProps) {
  const qrSrc = startData.qrcodeData
    ? `data:image/png;base64,${startData.qrcodeData}`
    : startData.qrcode ?? ''

  return (
    <div className="card" style={{ maxWidth: 480, margin: '0 auto', padding: 0 }}>
      <div className="card-body" style={{ textAlign: 'center', padding: '32px 24px' }}>
        {expired ? (
          <div className="channel-qr-expired">
            <div className="channel-qr-expired-title">二维码已过期</div>
            <div className="channel-qr-expired-sub">请刷新后重新扫描</div>
            <Button variant="primary" onClick={onRefresh}>
              刷新二维码
            </Button>
          </div>
        ) : (
          <>
            <div className="channel-qr-prompt">
              请使用企业微信扫码
              <span className="channel-qr-scan">
                扫一扫 <span className="channel-qr-arrow">→</span>
              </span>
            </div>
            <div className="channel-qr-img">
              {qrSrc ? (
                <img src={qrSrc} alt="企业微信扫码" />
              ) : (
                <div className="channel-qr-placeholder">二维码加载中…</div>
              )}
            </div>
            <div className="channel-qr-caption">扫码添加渠道账号</div>
            <div className="channel-qr-hint">二维码 60 秒内有效，过期后请刷新</div>
            <div className="channel-qr-countdown">剩余 {countdown} 秒</div>
          </>
        )}
        <div style={{ marginTop: 24, display: 'flex', gap: 10, justifyContent: 'center' }}>
          <Button variant="secondary" onClick={onBack}>
            上一步
          </Button>
          {!expired && (
            <Button variant="primary" onClick={onNext}>
              我已完成扫码，下一步
            </Button>
          )}
          {expired && (
            <Button variant="primary" onClick={onRefresh}>
              刷新
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ============================ verify ============================ */
interface StepVerifyProps {
  userInfo: WecomUserInfo | null
  verifyError: string | null
  submitting: boolean
  onBack: () => void
  onRescan: () => void
  onSubmit: (code: string) => void
}

function CodeInputs({
  onSubmit,
  disabled,
}: {
  onSubmit: (code: string) => void
  disabled: boolean
}) {
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', ''])
  const refs = useRef<Array<HTMLInputElement | null>>([])

  const focusAt = (i: number) => {
    const el = refs.current[i]
    if (el) {
      el.focus()
      el.select()
    }
  }

  const handleChange = (i: number, val: string) => {
    const clean = val.replace(/\D/g, '')
    if (clean === '') {
      const next = [...digits]
      next[i] = ''
      setDigits(next)
      return
    }
    const next = [...digits]
    let idx = i
    for (const ch of clean.split('')) {
      if (idx > 5) break
      next[idx] = ch
      idx += 1
    }
    setDigits(next)
    focusAt(Math.min(idx, 5))
  }

  const handleKeyDown = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      e.preventDefault()
      if (digits[i]) {
        const next = [...digits]
        next[i] = ''
        setDigits(next)
      } else if (i > 0) {
        const next = [...digits]
        next[i - 1] = ''
        setDigits(next)
        focusAt(i - 1)
      }
    } else if (e.key === 'ArrowLeft' && i > 0) {
      focusAt(i - 1)
    } else if (e.key === 'ArrowRight' && i < 5) {
      focusAt(i + 1)
    }
  }

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (!text) return
    const next = ['', '', '', '', '', '']
    for (let k = 0; k < text.length; k += 1) next[k] = text[k]
    setDigits(next)
    focusAt(Math.min(text.length, 5))
  }

  const code = digits.join('')
  const complete = code.length === 6

  return (
    <>
      <div className="channel-verify-inputs">
        {digits.map((d, i) => (
          <span key={i} style={{ display: 'contents' }}>
            {i === 3 && <span className="channel-verify-sep">·</span>}
            <input
              ref={(el) => {
                refs.current[i] = el
              }}
              className="channel-verify-box"
              maxLength={1}
              inputMode="numeric"
              autoComplete="one-time-code"
              value={d}
              disabled={disabled}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              onPaste={handlePaste}
              onFocus={(e) => e.target.select()}
            />
          </span>
        ))}
      </div>
      <button
        className="btn btn-primary"
        style={{ marginTop: 16 }}
        disabled={!complete || disabled}
        onClick={() => onSubmit(code)}
      >
        确认
      </button>
    </>
  )
}

export function StepVerify({
  userInfo,
  verifyError,
  submitting,
  onBack,
  onRescan,
  onSubmit,
}: StepVerifyProps) {
  const initial = userInfo?.nickname?.[0] ?? userInfo?.realname?.[0] ?? '微'
  const name = userInfo?.nickname ?? userInfo?.realname ?? '企业微信账号'
  const meta =
    [userInfo?.corpName, userInfo?.realname].filter((x): x is string => Boolean(x) && x !== name).join('·') ||
    '等待手机端确认'

  return (
    <div className="card" style={{ maxWidth: 760, margin: '0 auto', padding: 0 }}>
      <div className="card-body" style={{ padding: '28px 24px' }}>
        <div className="channel-verify-grid">
          <div className="channel-verify-left">
            <div className="channel-verify-tag">请在企业微信上确认登录</div>
            <div className="channel-verify-profile">
              <div className="channel-verify-avatar">{initial}</div>
              <div className="channel-verify-name">{name}</div>
              <div className="channel-verify-meta">{meta}</div>
            </div>
            <button className="channel-verify-back" onClick={onBack}>
              返回
            </button>
          </div>
          <div className="channel-verify-right">
            <div className="channel-verify-title">请输入验证码</div>
            <div className="channel-verify-subtitle">请输入扫描后，手机接收到的验证码</div>
            <CodeInputs onSubmit={onSubmit} disabled={submitting} />
            {verifyError && <div className="channel-verify-error">{verifyError}</div>}
            <div className="channel-verify-hint">6 位数字，60 秒内有效</div>
            <button className="channel-verify-back-link" onClick={onRescan}>
              返回重新扫码
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ============================ done ============================ */
export function StepDone() {
  return (
    <div className="card" style={{ maxWidth: 480, margin: '0 auto', padding: 0 }}>
      <div className="card-body" style={{ textAlign: 'center', padding: '36px 24px' }}>
        <div className="channel-done-icon">
          <CheckCircle2 size={56} />
        </div>
        <div className="channel-done-title">添加成功</div>
        <div className="channel-done-sub">企业微信账号已成功托管，即将跳转至账号列表…</div>
      </div>
    </div>
  )
}
