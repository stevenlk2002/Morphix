import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, MoreHorizontal, ChevronLeft, ChevronRight, Bot, AlertTriangle } from 'lucide-react'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'
import { botsApi } from '../../api/client'
import './Bots.css'

/** 机器人卡片（列表展示用）。 */
interface BotCard {
  id: string
  name: string
  type: string
  status: 'online' | 'training' | 'offline'
  desc: string
  tag: string
  createdAt: string
  updatedAt: string
}

/** 轮播 slide 配置。 */
interface BannerSlide {
  tag: string
  title: string
  btn: string
}

/** 轮播内容：用前必读 / 新功能。 */
const BANNER_SLIDES: BannerSlide[] = [
  { tag: '用前必读', title: '两分钟教你玩转Morphix', btn: '立即查看 ›' },
  { tag: '新功能', title: '智能机器人训练中心', btn: '去体验 ›' },
]

/** 机器人类型由 project / workflow 推断（中文业务类型）。 */
function mapBotType(raw: any): string {
  const workflow: string = (raw.workflow || '').toString()
  const project: string = (raw.project || '').toString()
  if (workflow.includes('接待') || project.includes('接待')) return '接待机器人'
  if (workflow.includes('销售') || workflow.includes('成交') || workflow.includes('询盘')) return '销售机器人'
  if (workflow.includes('售后') || workflow.includes('客服') || workflow.includes('问答')) return '问答机器人'
  if (workflow.includes('测试') || project.includes('QA')) return '问答机器人'
  return '问答机器人'
}

/** 标签由 project 派生，兜底「通用」。 */
function mapBotTag(project: any): string {
  const p: string = (project || '').toString()
  if (p === 'Global Fit') return '出海'
  if (p === 'QA') return '测试'
  if (p === 'Morphix') return '通用'
  return p || '通用'
}

/**
 * 把后端 GET /api/bots 返回的裸记录映射成前端卡片结构 BotCard。
 * 后端记录字段：id, name, project, status, workflow, tone, trainingPrompt,
 * score, createdAt, updatedAt。
 */
function mapBot(raw: any): BotCard {
  const status: BotCard['status'] =
    raw.status === 'online' || raw.status === 'training' ? raw.status : 'offline'
  const descRaw: string = (raw.trainingPrompt || raw.tone || '').toString().trim()
  const desc: string = descRaw
    ? descRaw.length > 40
      ? `${descRaw.slice(0, 40)}…`
      : descRaw
    : '暂无描述'
  const createdAt: string = raw.createdAt || raw.created_at || ''
  const updatedAt: string = raw.updatedAt || raw.updated_at || createdAt || ''
  return {
    id: raw.id,
    name: raw.name || '',
    type: mapBotType(raw),
    status,
    desc,
    tag: mapBotTag(raw.project),
    createdAt,
    updatedAt,
  }
}

type SortKey = '' | 'createdAt' | 'updatedAt' | 'name'
type SortDir = 'asc' | 'desc'

/**
 * 对话机器人列表页（/bots）。
 * 真实数据来自后端 GET /api/bots（经 botsApi.list 加载并 mapBot 映射）；
 * 轮播 Banner、筛选栏、创建弹窗、卡片网格由本地状态驱动。
 */
export default function BotsPage() {
  const navigate = useNavigate()

  const [bots, setBots] = useState<BotCard[]>([])

  // ---- 轮播 ----
  const [current, setCurrent] = useState(0)
  const timerRef = useRef<number | null>(null)

  const startAuto = () => {
    if (timerRef.current) window.clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      setCurrent((c) => (c + 1) % BANNER_SLIDES.length)
    }, 4500)
  }
  const stopAuto = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }
  useEffect(() => {
    startAuto()
    return stopAuto
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- 加载真实机器人列表（后端 /api/bots） ----
  useEffect(() => {
    let alive = true
    botsApi
      .list()
      .then((raw) => {
        if (!alive) return
        setBots(raw.map((item: unknown) => mapBot(item)))
      })
      .catch((e: unknown) => {
        toast(`加载机器人列表失败：${e instanceof Error ? e.message : String(e)}`)
      })
    return () => {
      alive = false
    }
  }, [])

  // ---- 筛选 ----
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [template, setTemplate] = useState('全部模板')
  const [sortKey, setSortKey] = useState<SortKey>('')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // ---- 弹窗 / 下拉 ----
  const [createOpen, setCreateOpen] = useState(false)
  const [moreOpenId, setMoreOpenId] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null)

  const filteredBots = useMemo(() => {
    const kw = search.trim().toLowerCase()
    let list = bots.filter((b) => {
      if (kw && !b.name.toLowerCase().includes(kw)) return false
      if (template !== '全部模板' && b.type !== template) return false
      return true
    })
    if (sortKey) {
      const dir = sortDir === 'asc' ? 1 : -1
      list = [...list].sort((a, b) => {
        if (sortKey === 'name') return a.name.localeCompare(b.name, 'zh') * dir
        return a[sortKey].localeCompare(b[sortKey]) * dir
      })
    }
    return list
  }, [bots, search, template, sortKey, sortDir])

  const handleBannerClick = () => toast('演示环境：该功能未接入')

  const openMore = (id: string) => setMoreOpenId((prev) => (prev === id ? null : id))
  const closeMore = () => setMoreOpenId(null)

  const handleMoreAction = (label: string) => {
    closeMore()
    toast(`演示环境：${label}未接入`)
  }

  const handleDeleteClick = (id: string, name: string) => {
    setMoreOpenId(null)
    setConfirmDelete({ id, name })
  }

  const handleConfirmDelete = async () => {
    if (!confirmDelete) return
    const id = confirmDelete.id
    const name = confirmDelete.name
    try {
      await botsApi.delete(id)
      setBots((prev) => prev.filter((b) => b.id !== id))
      toast(`已删除：${name}`)
    } catch (e) {
      toast(`删除失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setConfirmDelete(null)
    }
  }

  return (
    <div className="bots-page">
      {/* 轮播 Banner */}
      <div className="banner-carousel" onMouseEnter={stopAuto} onMouseLeave={startAuto}>
        <div className="banner-slides" style={{ transform: `translateX(-${current * 100}%)` }}>
          {BANNER_SLIDES.map((slide, idx) => (
            <div className="banner-slide" key={idx}>
              <div className="banner-slide-content">
                <span className="banner-slide-tag">{slide.tag}</span>
                <div className="banner-slide-title">{slide.title}</div>
                <button className="banner-slide-btn" type="button" onClick={handleBannerClick}>
                  {slide.btn}
                </button>
              </div>
              <svg className="banner-slide-illustration" viewBox="0 0 180 120" fill="none">
                <circle cx="90" cy="60" r="40" fill="#ffffff" opacity="0.5" />
                <path
                  d="M70 60l15 15 30-30"
                  stroke="#c9a87c"
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="90" cy="35" r="8" fill="#c9a87c" opacity="0.6" />
              </svg>
            </div>
          ))}
        </div>
        <button
          className="banner-nav banner-prev"
          type="button"
          onClick={() => setCurrent((c) => (c - 1 + BANNER_SLIDES.length) % BANNER_SLIDES.length)}
          aria-label="上一张"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          className="banner-nav banner-next"
          type="button"
          onClick={() => setCurrent((c) => (c + 1) % BANNER_SLIDES.length)}
          aria-label="下一张"
        >
          <ChevronRight size={16} />
        </button>
        <div className="banner-dots">
          {BANNER_SLIDES.map((_, idx) => (
            <button
              key={idx}
              type="button"
              className={`banner-dot ${idx === current ? 'active' : ''}`}
              onClick={() => setCurrent(idx)}
              aria-label={`第 ${idx + 1} 张`}
            />
          ))}
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="filter-bar">
        <div className="filter-search">
          <Search size={16} className="filter-search-icon" />
          <input
            className="filter-input"
            placeholder="搜索机器人名称"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && setSearch(searchInput)}
          />
        </div>
        <Button variant="primary" size="sm" icon={<Search size={16} />} onClick={() => setSearch(searchInput)}>
          搜索
        </Button>
        <select
          className="filter-select"
          style={{ marginLeft: 'auto' }}
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
        >
          <option value="全部模板">全部模板</option>
          <option value="接待机器人">接待机器人</option>
          <option value="问答机器人">问答机器人</option>
        </select>
        <select
          className="filter-select"
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
        >
          <option value="" disabled>
            排序方式
          </option>
          <option value="createdAt">创建日期</option>
          <option value="updatedAt">更新日期</option>
          <option value="name">名称排序</option>
        </select>
        <select
          className="filter-select"
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value as SortDir)}
        >
          <option value="asc">时间升序</option>
          <option value="desc">时间降序</option>
        </select>
      </div>

      {/* 机器人卡片网格 */}
      <div className="bot-card-grid">
        <div className="bot-card create-entry" onClick={() => setCreateOpen(true)}>
          <div className="create-entry-inner">
            <div className="create-entry-plus"><Plus size={28} /></div>
            <div className="create-entry-text">创建机器人</div>
          </div>
        </div>
        {filteredBots.map((bot) => {
          const isOnline = bot.status === 'online'
          const statusText =
            bot.status === 'training' ? '训练中' : bot.status === 'offline' ? '未上线' : '已上线'
          const dotColor =
            bot.status === 'training'
              ? 'var(--warning)'
              : bot.status === 'offline'
                ? 'var(--text-tertiary)'
                : 'var(--success)'
          const statusBadgeClass =
            bot.status === 'training'
              ? 'badge-warning'
              : bot.status === 'offline'
                ? 'badge-offline'
                : 'badge-success'
          return (
            <div key={bot.id} className="bot-card" onClick={() => navigate(`/bots/${bot.id}`)}>
              <span className={`bot-card-status badge ${statusBadgeClass}`}>
                {statusText}
              </span>
              <div className="bot-card-header">
                <div className={`bot-avatar ${isOnline ? '' : 'bot-avatar-alt'}`}>
                  <Bot size={20} />
                </div>
                <div className="bot-info">
                  <div className="bot-name">{bot.name}</div>
                  <div className="bot-meta">
                    <span className="bot-meta-dot" style={{ color: dotColor }} />
                    {bot.type} · {statusText}
                  </div>
                </div>
              </div>
              <div className="bot-desc">{bot.desc}</div>
              <div className="bot-tags">
                <span className="badge badge-default">{bot.tag}</span>
              </div>
              <div className="bot-actions">
                {isOnline ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/bots/${bot.id}`)
                    }}
                  >
                    训练调整
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        toast('机器人已上线')
                      }}
                    >
                      上线
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/bots/${bot.id}`)
                      }}
                    >
                      训练调整
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/bots/${bot.id}/orchestrate`)
                      }}
                    >
                      流程编辑
                    </Button>
                  </>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="btn-more"
                  icon={<MoreHorizontal size={16} />}
                  onClick={(e) => {
                    e.stopPropagation()
                    openMore(bot.id)
                  }}
                />
                {moreOpenId === bot.id && (
                  <>
                    <div className="more-backdrop" onClick={(e) => { e.stopPropagation(); closeMore() }} />
                    <div className="more-menu" onClick={(e) => e.stopPropagation()}>
                      <div className="more-item" onClick={() => handleMoreAction('复制机器人ID')}>
                        复制机器人ID
                      </div>
                      <div
                        className="more-item more-item-danger"
                        onClick={() => handleDeleteClick(bot.id, bot.name)}
                      >
                        删除
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="bot-updated">编辑于 {bot.updatedAt}</div>
            </div>
          )
        })}
      </div>

      {/* 创建机器人弹窗 */}
      {createOpen && (
        <div className="modal-overlay" onClick={() => setCreateOpen(false)}>
          <div className="modal-content create-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">创建机器人</h3>
            <div className="create-cards">
              <div
                className="bot-card create-card"
                onClick={(e) => {
                  e.stopPropagation()
                  setCreateOpen(false)
                  navigate('/bots/create?mode=template')
                }}
              >
                <div className="bot-card-header">
                  <div className="bot-avatar">模</div>
                  <div className="bot-info">
                    <div className="bot-name">从模板创建</div>
                    <div className="bot-meta">使用预制模板进行创建</div>
                  </div>
                </div>
                <div className="create-card-illus">
                  <svg viewBox="0 0 240 100" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="从模板创建示意图">
                    {/* 叠放的模板卡片 */}
                    <rect x="26" y="46" width="42" height="30" rx="6" fill="var(--border)" />
                    <rect x="18" y="38" width="42" height="30" rx="6" fill="var(--surface)" stroke="var(--border)" strokeWidth="1.5" />
                    <rect x="10" y="30" width="46" height="34" rx="6" fill="var(--primary-light)" stroke="var(--primary)" strokeWidth="1.5" />
                    {/* 卡片内文字占位线 */}
                    <rect x="16" y="46" width="22" height="3" rx="1.5" fill="var(--primary)" opacity="0.45" />
                    <rect x="16" y="53" width="15" height="3" rx="1.5" fill="var(--primary)" opacity="0.3" />
                    {/* 选中卡片的勾选标记 */}
                    <circle cx="47" cy="42" r="8" fill="var(--success)" />
                    <path d="M43 42l3 3 5-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    {/* 连线箭头：模板 -> 机器人 */}
                    <path d="M60 47H150" stroke="var(--border)" strokeWidth="2" strokeDasharray="5 5" />
                    <path d="M146 43l5 4-5 4" stroke="var(--text-tertiary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    {/* 机器人头像 */}
                    <circle cx="182" cy="47" r="24" fill="var(--primary)" />
                    <path d="M174 23v-6 M190 23v-6" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" />
                    <circle cx="174" cy="42" r="3" fill="#fff" />
                    <circle cx="190" cy="42" r="3" fill="#fff" />
                    <path d="M174 54c3 3 8 3 11 0" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" />
                  </svg>
                </div>
                <ul className="create-card-points">
                  <li>精选行业机器人模板</li>
                  <li>一键套用话术与配置</li>
                  <li>分钟级快速上线</li>
                </ul>
              </div>
              <div
                className="bot-card create-card"
                onClick={(e) => {
                  e.stopPropagation()
                  setCreateOpen(false)
                  navigate('/bots/create?mode=orchestrate')
                }}
              >
                <div className="bot-card-header">
                  <div className="bot-avatar bot-avatar-alt">编</div>
                  <div className="bot-info">
                    <div className="bot-name">从编排创建</div>
                    <div className="bot-meta">从0开始编排创建</div>
                  </div>
                </div>
                <div className="create-card-illus">
                  <svg viewBox="0 0 240 100" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="从编排创建示意图">
                    {/* 节点间连线 */}
                    <g stroke="var(--border)" strokeWidth="1.5">
                      <path d="M42 51H49" />
                      <path d="M114 51H121" />
                      <path d="M168 51H175" />
                    </g>
                    <g stroke="var(--text-tertiary)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M50 48l4 3-4 3" />
                      <path d="M122 48l4 3-4 3" />
                      <path d="M176 48l4 3-4 3" />
                    </g>
                    {/* 流程编排节点 */}
                    <rect x="4" y="38" width="38" height="26" rx="9" fill="var(--primary-light)" stroke="var(--primary)" strokeWidth="1.5" />
                    <rect x="58" y="38" width="56" height="26" rx="9" fill="var(--primary-light)" stroke="var(--primary)" strokeWidth="1.5" />
                    <rect x="130" y="38" width="38" height="26" rx="9" fill="var(--primary-light)" stroke="var(--primary)" strokeWidth="1.5" />
                    <rect x="184" y="38" width="52" height="26" rx="9" fill="var(--primary-light)" stroke="var(--primary)" strokeWidth="1.5" />
                    <text x="23" y="55" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--primary)">触发</text>
                    <text x="86" y="55" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--primary)">理解(LLM)</text>
                    <text x="149" y="55" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--primary)">工具</text>
                    <text x="210" y="55" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--primary)">回复</text>
                  </svg>
                </div>
                <ul className="create-card-points">
                  <li>可视化拖拽节点</li>
                  <li>自定义对话与分支逻辑</li>
                  <li>灵活对接多渠道</li>
                </ul>
              </div>
            </div>
            <div className="modal-actions">
              <Button variant="ghost" size="sm" onClick={() => setCreateOpen(false)}>
                取消
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
            <button
              className="modal-close"
              type="button"
              onClick={() => setConfirmDelete(null)}
              aria-label="关闭"
            >
              ×
            </button>
            <div className="confirm-icon">
              <AlertTriangle size={28} />
            </div>
            <h3 className="confirm-title">已选择：{confirmDelete.name}</h3>
            <p className="confirm-desc">删除后，将有0个会话取消托管，是否确认删除？</p>
            <div className="confirm-actions">
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(null)}>
                取消
              </Button>
              <Button variant="primary" size="sm" onClick={handleConfirmDelete}>
                删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
