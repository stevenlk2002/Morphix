/**
 * useWecomHosting —— 添加渠道账号向导状态机 + 轮询编排 hook。
 *
 * 步骤状态机：type → protocol → qr → verify → done
 * - beginScan: 调 startWecomScan，进入 qr，启动倒计时(ttl 秒)与轮询(每 2000ms)
 * - 轮询仅在后台获取 userInfo；loginType===2 → 停止轮询、toast、done 并跳转；
 *   轮询不再自动把 step 从 qr 切到 verify/waiting（由用户点「下一步」决定）
 * - submitCode: 调 verifyWecomCode；失败 → 停止轮询、保留 verify 页错误；
 *   成功继续轮询等待 loginType=2，成功后跳转
 * - 倒计时归零（仅 qr 态）→ 过期，回到 qr 并提供刷新（重新 beginScan）
 * - 组件卸载清理所有定时器（clearInterval + disposed 标志防内存泄漏）
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { channelsApi } from '../../api/client'
import { toast, errText } from '../../utils/toast'
import type { WecomUserInfo } from '../../types/channels'

/** 向导步骤。 */
export type HostStep = 'type' | 'protocol' | 'qr' | 'verify' | 'done'

/** 可选渠道（本期仅 wecom 接入真实协议）。 */
export type ChannelKey = 'wecom' | 'wechat' | 'whatsapp'

/** 接入协议。 */
export type ProtocolKey = 'ipod' | 'pc'

/** start 接口返回并前端持有的扫码数据。 */
export interface WecomStartData {
  uuid: string
  qrcodeData: string | null
  qrcode: string | null
  qrcodeKey: string
  ttl: number
  mock: boolean
}

const POLL_INTERVAL = 2000
const COUNTDOWN_INTERVAL = 1000

export interface UseWecomHostingResult {
  step: HostStep
  setStep: (s: HostStep) => void
  selectedChannel: ChannelKey | null
  setSelectedChannel: (c: ChannelKey | null) => void
  selectedProtocol: ProtocolKey
  setSelectedProtocol: (p: ProtocolKey) => void
  startData: WecomStartData | null
  userInfo: WecomUserInfo | null
  verifyError: string | null
  submitting: boolean
  qrCountdown: number
  expired: boolean
  polling: boolean
  beginScan: (teamId: string, channelType: 'wecom', protocol: ProtocolKey) => Promise<void>
  submitCode: (code: string) => Promise<void>
  goToVerify: () => void
  refresh: () => void
  reset: () => void
}

export function useWecomHosting(): UseWecomHostingResult {
  const navigate = useNavigate()
  const [step, setStep] = useState<HostStep>('type')
  const [selectedChannel, setSelectedChannel] = useState<ChannelKey | null>(null)
  const [selectedProtocol, setSelectedProtocol] = useState<ProtocolKey>('ipod')
  const [startData, setStartData] = useState<WecomStartData | null>(null)
  const [userInfo, setUserInfo] = useState<WecomUserInfo | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [qrCountdown, setQrCountdown] = useState(0)
  const [expired, setExpired] = useState(false)
  const [polling, setPolling] = useState(false)

  const pollTimer = useRef<number | null>(null)
  const countdownTimer = useRef<number | null>(null)
  const disposed = useRef(false)
  const stepRef = useRef<HostStep>(step)
  const uuidRef = useRef<string | null>(null)
  const lastParamsRef = useRef<{ teamId: string; channelType: 'wecom'; protocol: ProtocolKey } | null>(null)

  // 同步 step 到 ref，供轮询回调读取最新步骤而无需重建定时器
  useEffect(() => {
    stepRef.current = step
  }, [step])

  const clearPoll = useCallback(() => {
    if (pollTimer.current !== null) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
    setPolling(false)
  }, [])

  const clearCountdown = useCallback(() => {
    if (countdownTimer.current !== null) {
      clearInterval(countdownTimer.current)
      countdownTimer.current = null
    }
  }, [])

  const stopAll = useCallback(() => {
    clearPoll()
    clearCountdown()
  }, [clearPoll, clearCountdown])

  const goAccounts = useCallback(() => {
    navigate('/channels/accounts')
  }, [navigate])

  const pollTick = useCallback(async () => {
    const uuid = uuidRef.current
    if (!uuid || disposed.current) return
    try {
      const resp = await channelsApi.pollWecomLogin({ uuid })
      if (disposed.current) return
      if (resp.userInfo) setUserInfo(resp.userInfo)
      if (resp.loginType === 2) {
        stopAll()
        toast('企业微信账号托管成功')
        setStep('done')
        window.setTimeout(() => {
          if (!disposed.current) goAccounts()
        }, 1200)
        return
      }
      // 不再自动从二维码页跳转；轮询仅用于提前获取 userInfo/登录态。
    } catch (e) {
      // 轮询异常不阻断流程，等待下次重试（避免刷屏不 toast）
      console.warn('[useWecomHosting] poll failed:', e)
    }
  }, [goAccounts, stopAll])

  const beginScan = useCallback(
    async (teamId: string, channelType: 'wecom', protocol: ProtocolKey) => {
      if (disposed.current) return
      lastParamsRef.current = { teamId, channelType, protocol }
      setSubmitting(true)
      setVerifyError(null)
      setExpired(false)
      setUserInfo(null)
      try {
        const resp = await channelsApi.startWecomScan({ teamId, channelType, name: undefined })
        if (disposed.current) return
        const data: WecomStartData = {
          uuid: resp.uuid,
          qrcodeData: resp.qrcodeData,
          qrcode: resp.qrcode,
          qrcodeKey: resp.qrcodeKey,
          ttl: resp.ttl,
          mock: resp.mock,
        }
        uuidRef.current = resp.uuid
        setStartData(data)
        // 用户要求二维码至少停留 60 秒，即使后端 ttl 更长也以 60 秒为展示下限
        setQrCountdown(Math.min(resp.ttl, 60))
        setStep('qr')
        clearPoll()
        clearCountdown()
        countdownTimer.current = window.setInterval(() => {
          setQrCountdown((prev) => (prev <= 1 ? 0 : prev - 1))
        }, COUNTDOWN_INTERVAL)
        setPolling(true)
        pollTimer.current = window.setInterval(() => {
          void pollTick()
        }, POLL_INTERVAL)
      } catch (e) {
        toast(`启动扫码失败：${errText(e)}`)
      } finally {
        if (!disposed.current) setSubmitting(false)
      }
    },
    [clearPoll, clearCountdown, pollTick]
  )

  const goToVerify = useCallback(() => {
    setVerifyError(null)
    setStep('verify')
  }, [])

  const submitCode = useCallback(
    async (code: string) => {
      const data = startData
      if (!data) return
      setSubmitting(true)
      setVerifyError(null)
      try {
        const resp = await channelsApi.verifyWecomCode({
          uuid: data.uuid,
          qrcodeKey: data.qrcodeKey,
          code,
        })
        if (disposed.current) return
        if (!resp.ok) {
          const msg = '验证码错误，请重新输入'
          setVerifyError(msg)
          toast(msg)
          // 验证码错误后必须停止轮询，防止后续 poll 到 loginType=2 自动跳 done
          stopAll()
          return
        }
        // 校验通过：skip 时无需再输入，直接进入完成态；否则继续轮询等待 loginType=2
        if (resp.skip) {
          stopAll()
          setStep('done')
        }
      } catch (e) {
        const msg = errText(e)
        setVerifyError(msg)
        toast(`验证失败：${msg}`)
      } finally {
        if (!disposed.current) setSubmitting(false)
      }
    },
    [startData]
  )

  const refresh = useCallback(() => {
    const p = lastParamsRef.current
    if (!p) return
    void beginScan(p.teamId, p.channelType, p.protocol)
  }, [beginScan])

  const reset = useCallback(() => {
    stopAll()
    uuidRef.current = null
    lastParamsRef.current = null
    setStartData(null)
    setUserInfo(null)
    setSelectedChannel(null)
    setSelectedProtocol('ipod')
    setVerifyError(null)
    setSubmitting(false)
    setQrCountdown(0)
    setExpired(false)
    setStep('type')
  }, [stopAll])

  // 二维码倒计时归零 → 过期，回到 qr 并提供刷新
  useEffect(() => {
    if (
      qrCountdown === 0 &&
      startData &&
      !expired &&
      (step === 'qr' || step === 'verify')
    ) {
      stopAll()
      setExpired(true)
      setStep('qr')
    }
  }, [qrCountdown, startData, expired, step, stopAll])

  // 回退到 type/protocol 时取消进行中的扫码轮询与倒计时
  useEffect(() => {
    if (step === 'type' || step === 'protocol') {
      stopAll()
      setExpired(false)
    }
  }, [step, stopAll])

  // 组件卸载清理定时器 + 标记 disposed 防止延迟回调误触
  useEffect(() => {
    disposed.current = false
    return () => {
      disposed.current = true
      if (pollTimer.current !== null) clearInterval(pollTimer.current)
      if (countdownTimer.current !== null) clearInterval(countdownTimer.current)
    }
  }, [])

  return {
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
    polling,
    beginScan,
    submitCode,
    goToVerify,
    refresh,
    reset,
  }
}

export default useWecomHosting
