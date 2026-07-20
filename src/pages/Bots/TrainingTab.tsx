import { useState, useRef, useEffect } from 'react'
import {
  RefreshCw,
  Copy,
  ThumbsUp,
  ThumbsDown,
  Send,
  Mic,
  Plus,
  Trash2,
  HelpCircle,
  Bot,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Upload,
} from 'lucide-react'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'
import { trainingApi, TrainingRecordDTO, TrainingMessageDTO } from '../../api/client'
import KnowledgeTab from './KnowledgeTab'
import MaterialTab from './MaterialTab'
import './TrainingTab.css'

/** 传给训练页的机器人引用。 */
interface BotRef {
  id: string
  name?: string
}

/** 对话消息角色。 */
type MessageRole = 'user' | 'ai'

/** 训练对话单条消息。 */
interface Message {
  id: string
  role: MessageRole
  content: string
  /** AI 消息的记录 ID，用于「复制ID」。 */
  recordId?: string
  like?: boolean
  dislike?: boolean
}

/** 训练记录（含好评/差评/总回复统计）。 */
interface TrainHistory {
  id: string
  title: string
  time: string
  good: number
  bad: number
  total: number
}

/** 欢迎语卡片类型。 */
type WelcomeTabType = 'text' | 'image' | 'video' | 'file' | 'link'

/** 单张欢迎语卡片。 */
interface WelcomeCard {
  id: string
  activeTab: WelcomeTabType
  text: string
  link: string
  linkTitle: string
  linkDesc: string
}

/** 训练主区域 Tab。 */
type TrainTabKey = 'chat' | 'knowledge' | 'material'

/** 欢迎语 Tab 定义。 */
const WELCOME_TABS: { key: WelcomeTabType; label: string }[] = [
  { key: 'text', label: '文本' },
  { key: 'image', label: '图片' },
  { key: 'video', label: '视频' },
  { key: 'file', label: '文件' },
  { key: 'link', label: '卡片链接' },
]

/** 生成稳定唯一 id（前端乐观更新用）。 */
function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

/** 生成 AI 消息记录 ID（msg-YYYYMMDD-NNN）。 */
function genRecordId(): string {
  const d = new Date()
  const pad = (x: number) => String(x).padStart(2, '0')
  const date = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
  const seq = String(Math.floor(Math.random() * 900) + 100)
  return `msg-${date}-${seq}`
}

/** 后端 TrainingRecordDTO → 前端 TrainHistory。 */
function toHistory(dto: TrainingRecordDTO): TrainHistory {
  return {
    id: dto.id,
    title: dto.title,
    time: dto.createdAt,
    good: dto.goodCount,
    bad: dto.badCount,
    total: dto.totalCount,
  }
}

/** 后端 TrainingMessageDTO → 前端 Message。 */
function toMessage(dto: TrainingMessageDTO): Message {
  return {
    id: dto.id,
    role: dto.role as MessageRole,
    content: dto.content,
    recordId: dto.recordRef || undefined,
    like: dto.feedback === 'like',
    dislike: dto.feedback === 'dislike',
  }
}

/**
 * 训练调整 Tab（深度还原 prototype robot-train）。
 * 包含常驻的机器人属性面板（可折叠）与三 Tab：训练对话 / 知识内容 / 素材内容。
 * 训练对话内：左侧训练记录子栏 + 可拖拽 resizer + 右侧训练对话。
 * 数据全部来自真实后端（trainingApi），发送由前端 1s 模拟 AI 后落库。
 */
export default function TrainingTab({ bot }: { bot: BotRef }) {
  const [activeTrainTab, setActiveTrainTab] = useState<TrainTabKey>('chat')
  const [history, setHistory] = useState<TrainHistory[]>([])
  const [conversations, setConversations] = useState<Record<string, Message[]>>({})
  const [activeHistoryId, setActiveHistoryId] = useState('')
  const [loading, setLoading] = useState(false)

  const [input, setInput] = useState('')

  const [propsCollapsed, setPropsCollapsed] = useState(false)
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const [historyWidth, setHistoryWidth] = useState(240)

  const [botName, setBotName] = useState(bot.name ?? '')
  const [botDesc, setBotDesc] = useState('')
  const [supportMedia, setSupportMedia] = useState(false)
  const [waitText, setWaitText] = useState('')
  const [interruptEnabled, setInterruptEnabled] = useState(true)

  const [welcomeCards, setWelcomeCards] = useState<WelcomeCard[]>([])

  const layoutRef = useRef<HTMLDivElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  const messages = conversations[activeHistoryId] ?? []

  /** 加载某条训练记录的消息流。 */
  const loadMessages = async (recordId: string) => {
    try {
      const dtos = await trainingApi.listMessages(recordId)
      setConversations((prev) => ({ ...prev, [recordId]: dtos.map(toMessage) }))
    } catch (e) {
      toast(`加载对话失败：${(e as Error).message}`)
    }
  }

  /** 进入页面 / 切换 bot：拉取训练记录，选中首条并加载其消息。 */
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const recs = await trainingApi.listRecords(bot.id)
        if (cancelled) return
        const mapped = recs.map(toHistory)
        setHistory(mapped)
        const firstId = mapped[0]?.id ?? ''
        setActiveHistoryId(firstId)
        if (firstId) {
          const dtos = await trainingApi.listMessages(firstId)
          if (!cancelled) {
            setConversations({ [firstId]: dtos.map(toMessage) })
          }
        } else {
          setConversations({})
        }
      } catch (e) {
        if (!cancelled) toast(`加载训练记录失败：${(e as Error).message}`)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.id])

  /** 切换训练记录（点击左侧子栏）。 */
  const selectHistory = async (id: string) => {
    setActiveHistoryId(id)
    if (id && !conversations[id]) {
      await loadMessages(id)
    }
  }

  /** 追加一条用户消息，并在 1s 后追加一条模拟 AI 回复（带 recordId，落库）。 */
  const sendUserMessage = (content: string) => {
    const text = content.trim()
    if (!text) return
    const historyId = activeHistoryId
    if (!historyId) {
      toast('请先新建训练')
      return
    }
    const userMsg: Message = { id: genId(), role: 'user', content: text }
    // 乐观更新：先展示用户消息
    setConversations((prev) => ({
      ...prev,
      [historyId]: [...(prev[historyId] ?? []), userMsg],
    }))
    // 落库 user 消息
    trainingApi
      .addMessage(historyId, { role: 'user', content: text })
      .catch((e) => toast(`发送失败：${(e as Error).message}`))

    window.setTimeout(() => {
      const recordRef = genRecordId()
      const aiMsg: Message = {
        id: genId(),
        role: 'ai',
        content: '好的，我明白了。让我为您提供更详细的信息...',
        recordId: recordRef,
      }
      setConversations((prev) => {
        const nextConv = [...(prev[historyId] ?? []), aiMsg]
        setHistory((hPrev) =>
          hPrev.map((h) =>
            h.id === historyId
              ? { ...h, total: nextConv.filter((m) => m.role === 'ai').length }
              : h
          )
        )
        return { ...prev, [historyId]: nextConv }
      })
      // 落库 ai 消息（带 recordRef）
      trainingApi
        .addMessage(historyId, { role: 'ai', content: aiMsg.content, recordRef })
        .catch((e) => toast(`AI 回复保存失败：${(e as Error).message}`))
    }, 1000)
  }

  const handleSend = () => {
    if (!input.trim()) return
    sendUserMessage(input)
    setInput('')
  }

  /** 复制文本并提示。 */
  const copyText = (text: string) => {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => undefined)
    }
    toast('复制成功')
  }

  /** 再问一次：重发被点击的用户消息自身内容。 */
  const handleRegenerate = (msgId: string) => {
    const msg = messages.find((m) => m.id === msgId)
    if (!msg || msg.role !== 'user') return
    sendUserMessage(msg.content)
  }

  /**
   * 点赞 / 点踩（互斥），调用后端重算该记录 good/bad/total。
   * 用返回的 record 重算本地 good/bad/total，保证与后端一致。
   */
  const updateScore = async (msgId: string, type: 'like' | 'dislike') => {
    const historyId = activeHistoryId
    const current = conversations[historyId] ?? []
    const target = current.find((m) => m.id === msgId)
    if (!target || target.role !== 'ai') return

    // 计算下一份 feedback：互斥；再次点击同项则取消
    const wantLike = type === 'like'
    const nextFeedback: 'like' | 'dislike' | null = wantLike
      ? target.like
        ? null
        : 'like'
      : target.dislike
        ? null
        : 'dislike'

    // 乐观更新本地消息状态
    const optimistic = current.map((m) =>
      m.id === msgId
        ? { ...m, like: nextFeedback === 'like', dislike: nextFeedback === 'dislike' }
        : m
    )
    setConversations((prev) => ({ ...prev, [historyId]: optimistic }))

    try {
      const res = await trainingApi.updateFeedback(msgId, nextFeedback)
      setHistory((prev) =>
        prev.map((h) =>
          h.id === historyId
            ? {
                ...h,
                good: res.record.goodCount,
                bad: res.record.badCount,
                total: res.record.totalCount,
              }
            : h
        )
      )
    } catch (e) {
      // 失败回滚本地消息状态
      setConversations((prev) => ({ ...prev, [historyId]: current }))
      toast(`更新反馈失败：${(e as Error).message}`)
    }
  }

  /** 新建训练：前端计算「训练历史N」，写入后端并设为 active。 */
  const handleNewTraining = async () => {
    const maxNum = history.reduce((max, h) => {
      const match = h.title.match(/训练历史(\d+)/)
      return match ? Math.max(max, parseInt(match[1], 10)) : max
    }, 0)
    const nextNum = maxNum + 1
    const title = `训练历史${nextNum}`
    try {
      const rec = await trainingApi.createRecord(bot.id, title)
      const item = toHistory(rec)
      setHistory((prev) => [item, ...prev])
      setConversations((prev) => ({ ...prev, [item.id]: [] }))
      setActiveHistoryId(item.id)
      toast('新建训练成功')
    } catch (e) {
      toast(`新建训练失败：${(e as Error).message}`)
    }
  }

  /** 删除训练记录：调后端级联删除，清理本地状态并切到首条。 */
  const handleDeleteHistory = async (id: string) => {
    try {
      await trainingApi.deleteRecord(id)
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`)
      return
    }
    const next = history.filter((h) => h.id !== id)
    setHistory(next)
    setConversations((prev) => {
      const copy = { ...prev }
      delete copy[id]
      return copy
    })
    if (activeHistoryId === id) {
      const firstId = next[0]?.id ?? ''
      setActiveHistoryId(firstId)
      if (firstId) await loadMessages(firstId)
    }
    toast('训练历史已删除')
  }

  /** 触发隐藏的文件选择框（批量上传训练问题）。 */
  const openTrainUpload = () => {
    if (uploadRef.current) {
      uploadRef.current.value = ''
      uploadRef.current.click()
    }
  }

  const handleTrainUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) toast(`已选择文件：${file.name}`)
  }

  /** 拖拽调整训练记录子栏宽度。 */
  const startResize = (e: React.MouseEvent) => {
    if (historyCollapsed) return
    const layout = layoutRef.current
    if (!layout) return
    const startX = e.clientX
    const startWidth = historyWidth
    const rect = layout.getBoundingClientRect()
    const minWidth = 180
    const maxWidth = Math.max(minWidth, rect.width * 0.55)
    const onMove = (ev: MouseEvent) => {
      let w = Math.round(startWidth + (ev.clientX - startX))
      w = Math.max(minWidth, Math.min(maxWidth, w))
      setHistoryWidth(w)
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  /* ===== 欢迎语卡片 ===== */
  const addWelcomeCard = () => {
    setWelcomeCards((prev) => [
      ...prev,
      { id: genId(), activeTab: 'text', text: '', link: '', linkTitle: '', linkDesc: '' },
    ])
  }

  const deleteWelcomeCard = (id: string) => {
    setWelcomeCards((prev) => prev.filter((c) => c.id !== id))
  }

  const switchWelcomeTab = (id: string, tab: WelcomeTabType) => {
    setWelcomeCards((prev) => prev.map((c) => (c.id === id ? { ...c, activeTab: tab } : c)))
  }

  const updateWelcomeField = (id: string, field: keyof WelcomeCard, value: string) => {
    setWelcomeCards((prev) => prev.map((c) => (c.id === id ? { ...c, [field]: value } : c)))
  }

  const insertNickname = (id: string) => {
    setWelcomeCards((prev) =>
      prev.map((c) => (c.id === id ? { ...c, text: c.text + '{{用户昵称}}' } : c))
    )
  }

  /** 当前激活 tab 是否已有内容（用于「请补全欢迎语」校验）。 */
  const welcomeHasContent = (c: WelcomeCard): boolean => {
    if (c.activeTab === 'text') return true
    if (c.activeTab === 'link') return !!(c.link.trim() || c.linkTitle.trim() || c.linkDesc.trim())
    return false
  }

  return (
    <div className="training-tab">
      {/* ===== 机器人属性面板（常驻左侧，可折叠） ===== */}
      <aside className={`train-props ${propsCollapsed ? 'collapsed' : ''}`}>
        <div className="train-props-header">
          <span className="props-title">机器人属性</span>
          <div className="props-actions">
            <Button variant="primary" size="sm" onClick={() => toast('已保存')}>
              保存
            </Button>
            <button
              className="train-props-toggle"
              title={propsCollapsed ? '展开机器人属性' : '折叠机器人属性'}
              onClick={() => setPropsCollapsed((v) => !v)}
            >
              {propsCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            </button>
          </div>
        </div>

        <div className="props-collapsed-hint">
          <Bot size={20} />
          <span>属性</span>
        </div>

        <div className="train-props-body">
          <div className="form-group">
            <label className="form-label">
              机器人名称 <span className="required">*</span>
            </label>
            <input
              className="input"
              value={botName}
              maxLength={30}
              onChange={(e) => setBotName(e.target.value)}
            />
            <div className="field-counter">
              {botName.length} / 30
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              机器人功能描述 <span className="required">*</span>
            </label>
            <textarea
              className="textarea"
              rows={5}
              placeholder="主要为耳鸣疾病的客户提供健康咨询、用药方案。"
              value={botDesc}
              maxLength={150}
              onChange={(e) => setBotDesc(e.target.value)}
            />
            <div className="field-counter">
              {botDesc.length} / 150
            </div>
          </div>

          <div className="form-group form-group-switch">
            <label className="form-label">是否支持识别客户的图片、语音、视频</label>
            <label className="switch">
              <input
                type="checkbox"
                checked={supportMedia}
                onChange={(e) => setSupportMedia(e.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>

          <div className="form-group">
            <label className="form-label">识别期间等待话术</label>
            <textarea
              className="textarea"
              rows={4}
              placeholder="由于图片、视频和语音的识别需要时间，在等待机器人识别的过程中，您给客户说点什么吧？比如：稍等我看一下哈~"
              value={waitText}
              onChange={(e) => setWaitText(e.target.value)}
            />
          </div>

          <div className="form-group form-group-switch">
            <label className="form-label">打断处理中消息</label>
            <label className="switch">
              <input
                type="checkbox"
                checked={interruptEnabled}
                onChange={(e) => setInterruptEnabled(e.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>

          <div className="form-group">
            <label className="form-label">
              添加欢迎语{' '}
              <span className="welcome-tip">
                <span className="tab-tooltip-bubble">
                  一条欢迎语仅代表一条消息，如需发送多条内容，请添加多条欢迎语
                </span>
                <HelpCircle size={14} />
              </span>
            </label>
            <div className="welcome-cards">
              {welcomeCards.map((card, idx) => (
                <div className="welcome-card" key={card.id}>
                  <div className="welcome-card-header">
                    <span className="welcome-card-title">欢迎语 {idx + 1}</span>
                    <button
                      className="welcome-card-delete"
                      title="删除欢迎语"
                      onClick={() => deleteWelcomeCard(card.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="welcome-tabs">
                    {WELCOME_TABS.map((t) => (
                      <div
                        key={t.key}
                        className={`welcome-tab ${card.activeTab === t.key ? 'active' : ''}`}
                        onClick={() => switchWelcomeTab(card.id, t.key)}
                      >
                        {t.label}
                      </div>
                    ))}
                  </div>
                  <div className="welcome-tab-contents">
                    {/* 文本 */}
                    <div
                      className={`welcome-tab-content ${card.activeTab === 'text' ? 'active' : ''}`}
                      data-tab="text"
                    >
                      <textarea
                        className="welcome-textarea"
                        placeholder="主动与客户说的第一句话，一般以提问结尾，也可以发送图片、语音、视频；通常为了使开口目的更聚焦，纯文字是够用的。例如:hello，我是Elsa老师，小朋友有什么英语学习的困扰呢？可以跟我说说我来帮你分析一下~"
                        value={card.text}
                        maxLength={200}
                        onChange={(e) => updateWelcomeField(card.id, 'text', e.target.value)}
                      />
                      <div className="welcome-footer">
                        <span className="welcome-counter">{card.text.length} / 200</span>
                        <button
                          className="welcome-nickname-btn"
                          onClick={() => insertNickname(card.id)}
                        >
                          <Plus size={12} /> 插入用户昵称
                        </button>
                      </div>
                    </div>
                    {/* 图片 */}
                    <div
                      className={`welcome-tab-content ${card.activeTab === 'image' ? 'active' : ''}`}
                      data-tab="image"
                    >
                      <div className="welcome-upload">
                        <div className="welcome-upload-icon">
                          <Upload size={28} />
                        </div>
                        <div className="welcome-upload-text">
                          拖拽图片至此，或者<span className="upload-link">上传图片</span>
                        </div>
                        <div className="welcome-upload-hint">最大可以上传15M的图片</div>
                      </div>
                    </div>
                    {/* 视频 */}
                    <div
                      className={`welcome-tab-content ${card.activeTab === 'video' ? 'active' : ''}`}
                      data-tab="video"
                    >
                      <div className="welcome-upload">
                        <div className="welcome-upload-icon">
                          <Upload size={28} />
                        </div>
                        <div className="welcome-upload-text">
                          拖拽视频至此，或者<span className="upload-link">上传视频</span>
                        </div>
                        <div className="welcome-upload-hint">最大可以上传20M的视频</div>
                      </div>
                    </div>
                    {/* 文件 */}
                    <div
                      className={`welcome-tab-content ${card.activeTab === 'file' ? 'active' : ''}`}
                      data-tab="file"
                    >
                      <div className="welcome-upload">
                        <div className="welcome-upload-icon">
                          <Upload size={28} />
                        </div>
                        <div className="welcome-upload-text">
                          拖拽文件至此，或者<span className="upload-link">上传文件</span>
                        </div>
                        <div className="welcome-upload-hint">最大可以上传50M的文件</div>
                      </div>
                    </div>
                    {/* 卡片链接 */}
                    <div
                      className={`welcome-tab-content ${card.activeTab === 'link' ? 'active' : ''}`}
                      data-tab="link"
                    >
                      <div className="welcome-link-form">
                        <div className="welcome-link-row">
                          <label>卡片链接</label>
                          <input
                            placeholder="请输入http或https开头的链接"
                            value={card.link}
                            onChange={(e) => updateWelcomeField(card.id, 'link', e.target.value)}
                          />
                        </div>
                        <div className="welcome-link-row">
                          <label>卡片标题</label>
                          <div style={{ flex: 1 }}>
                            <textarea
                              className="welcome-link-textarea"
                              rows={2}
                              placeholder="请输入卡片标题"
                              maxLength={30}
                              value={card.linkTitle}
                              onChange={(e) =>
                                updateWelcomeField(card.id, 'linkTitle', e.target.value)
                              }
                            />
                            <div className="welcome-link-counter">{card.linkTitle.length} / 30</div>
                          </div>
                        </div>
                        <div className="welcome-link-row">
                          <label>卡片描述</label>
                          <div style={{ flex: 1 }}>
                            <textarea
                              className="welcome-link-textarea"
                              rows={3}
                              placeholder="请输入卡片描述"
                              maxLength={80}
                              value={card.linkDesc}
                              onChange={(e) =>
                                updateWelcomeField(card.id, 'linkDesc', e.target.value)
                              }
                            />
                            <div className="welcome-link-counter">{card.linkDesc.length} / 80</div>
                          </div>
                        </div>
                        <div className="welcome-link-row">
                          <label>卡片封面</label>
                          <div className="welcome-cover-wrap">
                            <div className="welcome-cover-box">
                              <Plus size={18} />
                            </div>
                            <div className="welcome-cover-tip">建议尺寸 300×300</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  {card.activeTab !== 'text' && !welcomeHasContent(card) && (
                    <div className="welcome-error show">请补全欢迎语</div>
                  )}
                </div>
              ))}
            </div>
            <Button
              variant="secondary"
              size="sm"
              style={{ width: '100%' }}
              icon={<Plus size={14} />}
              onClick={addWelcomeCard}
            >
              添加欢迎语
            </Button>
          </div>
        </div>
      </aside>

      {/* ===== 主区域：三 Tab ===== */}
      <main className="train-main">
        <div className="train-tabs">
          <div
            className={`train-tab ${activeTrainTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTrainTab('chat')}
          >
            训练对话
          </div>
          <div
            className={`train-tab ${activeTrainTab === 'knowledge' ? 'active' : ''}`}
            onClick={() => setActiveTrainTab('knowledge')}
          >
            知识内容
          </div>
          <div
            className={`train-tab ${activeTrainTab === 'material' ? 'active' : ''}`}
            onClick={() => setActiveTrainTab('material')}
          >
            素材内容
          </div>
        </div>

        <div className="train-tab-content">
          {activeTrainTab === 'chat' && (
            <div className="train-chat-pane">
              <div
                className={`train-chat-layout ${historyCollapsed ? 'full' : ''}`}
                ref={layoutRef}
                style={{
                  gridTemplateColumns: historyCollapsed ? '1fr' : `${historyWidth}px 6px 1fr`,
                }}
              >
                {/* 训练记录子栏 */}
                <aside className="train-history">
                  <div className="train-history-header">
                    <span className="section-label">训练记录</span>
                    <Button
                      variant="primary"
                      size="sm"
                      icon={<Plus size={14} />}
                      onClick={handleNewTraining}
                    >
                      新建训练
                    </Button>
                  </div>
                  {loading ? (
                    <div className="train-history-loading">加载中…</div>
                  ) : (
                    <div className="train-history-list">
                      {history.length === 0 && (
                        <div className="train-history-empty">暂无训练记录</div>
                      )}
                      {history.map((h) => (
                        <div
                          key={h.id}
                          className={`train-history-item ${h.id === activeHistoryId ? 'active' : ''}`}
                          onClick={() => selectHistory(h.id)}
                        >
                          <div className="history-title">{h.title}</div>
                          <div className="history-time">{h.time}</div>
                          <div className="history-meta">
                            <span>好评 {h.good}</span>
                            <span>差评 {h.bad}</span>
                            <span>总回复 {h.total}</span>
                          </div>
                          <button
                            className="history-delete"
                            title="删除训练历史"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteHistory(h.id)
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </aside>

                {/* 拖拽调整宽度 */}
                <div
                  className="train-resizer"
                  onMouseDown={startResize}
                  title="拖拽调整训练记录宽度"
                />

                {/* 训练对话区 */}
                <div className="train-chat-area">
                  <div className="train-chat-header">
                    <span className="train-chat-title">训练对话</span>
                    <div className="train-chat-header-actions">
                      <span className="train-upload-bar" onClick={openTrainUpload}>
                        <Upload size={14} /> 批量上传训练问题
                      </span>
                      <input
                        ref={uploadRef}
                        type="file"
                        accept=".txt,.csv,.xlsx"
                        style={{ display: 'none' }}
                        onChange={handleTrainUpload}
                      />
                      <button
                        className="train-history-toggle"
                        title={historyCollapsed ? '展开训练记录' : '收起训练记录'}
                        onClick={() => setHistoryCollapsed((v) => !v)}
                      >
                        {historyCollapsed ? <PanelRightOpen size={16} /> : <PanelRightClose size={16} />}
                      </button>
                    </div>
                  </div>

                  <div className="train-chat-messages">
                    {messages.length === 0 && (
                      <div className="train-chat-empty">
                        {activeHistoryId ? '开始你的第一次训练对话吧' : '请选择或新建训练记录'}
                      </div>
                    )}
                    {messages.map((m) =>
                      m.role === 'user' ? (
                        <div key={m.id} className="train-message user">
                          <div className="msg-main">
                            <div className="msg-bubble">{m.content}</div>
                            <div className="msg-footer">
                              <div className="msg-footer-left">
                                <span className="msg-length">{m.content.length}</span>
                              </div>
                              <div className="msg-footer-right">
                                <button
                                  className="msg-icon-btn"
                                  title="再问一次"
                                  onClick={() => handleRegenerate(m.id)}
                                >
                                  <RefreshCw size={14} />
                                </button>
                                <button
                                  className="msg-icon-btn"
                                  title="复制"
                                  onClick={() => copyText(m.content)}
                                >
                                  <Copy size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div
                          key={m.id}
                          className="train-message bot"
                          data-record-id={m.recordId}
                        >
                          <div className="msg-avatar">
                            <Bot size={18} />
                          </div>
                          <div className="msg-main">
                            <div className="msg-bubble">{m.content}</div>
                            <div className="msg-footer">
                              <div className="msg-footer-left">
                                <span
                                  className="msg-copy-id"
                                  title="复制记录ID"
                                  onClick={() => copyText(m.recordId ?? '')}
                                >
                                  复制ID
                                </span>
                              </div>
                              <div className="msg-footer-right">
                                <button
                                  className="msg-icon-btn"
                                  title="复制"
                                  onClick={() => copyText(m.content)}
                                >
                                  <Copy size={14} />
                                </button>
                                <button
                                  className={`msg-icon-btn ${m.like ? 'active' : ''}`}
                                  title="点赞"
                                  onClick={() => updateScore(m.id, 'like')}
                                >
                                  <ThumbsUp size={14} />
                                </button>
                                <button
                                  className={`msg-icon-btn ${m.dislike ? 'active' : ''}`}
                                  title="点踩"
                                  onClick={() => updateScore(m.id, 'dislike')}
                                >
                                  <ThumbsDown size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    )}
                  </div>

                  <div className="train-chat-input">
                    <button className="btn-icon" title="语音输入">
                      <Mic size={18} />
                    </button>
                    <input
                      className="input"
                      placeholder="可以问我任何问题"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    />
                    <button className="train-send-btn" onClick={handleSend}>
                      <Send size={16} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTrainTab === 'knowledge' && (
            <div className="train-knowledge-pane">
              <KnowledgeTab bot={bot} />
            </div>
          )}

          {activeTrainTab === 'material' && (
            <div className="train-material-pane">
              <MaterialTab bot={bot} />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
