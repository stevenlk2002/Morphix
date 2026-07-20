import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, MoreHorizontal, ChevronLeft, ChevronRight, Bot } from 'lucide-react'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'
import './Bots.css'

/** 机器人卡片（列表展示用）。 */
interface BotCard {
  id: string
  name: string
  type: string
  status: 'online' | 'training'
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

/** 列表 mock 种子数据（纯前端，无后端依赖）。 */
const BOTS_MOCK: BotCard[] = [
  {
    id: 'yefengqiu',
    name: '野风秋大健康机器人',
    type: '接待机器人',
    status: 'online',
    desc: '专注于为中老年群体及慢性病管理人群提供科学、合规的健康咨询与生活方式指导服务。',
    tag: '接待',
    createdAt: '2026-07-01 10:12:30',
    updatedAt: '2026-07-05 09:20:11',
  },
  {
    id: 'fanfuni',
    name: '梵芙尼美妆销售机器人',
    type: '问答机器人',
    status: 'training',
    desc: '为高端美妆消费者提供专业、个性化的护肤与彩妆产品咨询与购买引导服务。',
    tag: '销售',
    createdAt: '2026-07-03 14:48:02',
    updatedAt: '2026-07-10 21:09:50',
  },
]

type SortKey = '' | 'createdAt' | 'updatedAt' | 'name'
type SortDir = 'asc' | 'desc'

/**
 * 对话机器人列表页（/bots）。
 * 纯前端 mock：轮播 Banner、筛选栏、创建弹窗、卡片网格，全部本地状态驱动。
 */
export default function BotsPage() {
  const navigate = useNavigate()

  const [bots] = useState<BotCard[]>(BOTS_MOCK)

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

  // ---- 筛选 ----
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [template, setTemplate] = useState('全部模板')
  const [sortKey, setSortKey] = useState<SortKey>('')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  // ---- 弹窗 / 下拉 ----
  const [createOpen, setCreateOpen] = useState(false)
  const [moreOpenId, setMoreOpenId] = useState<string | null>(null)

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

  const handleCreateCard = () => {
    setCreateOpen(false)
    toast('演示环境：创建流程未接入')
  }

  const openMore = (id: string) => setMoreOpenId((prev) => (prev === id ? null : id))
  const closeMore = () => setMoreOpenId(null)

  const handleMoreAction = (label: string) => {
    closeMore()
    toast(`演示环境：${label}未接入`)
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
        <select className="filter-select" value={template} onChange={(e) => setTemplate(e.target.value)}>
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
        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={16} />}
          style={{ marginLeft: 'auto' }}
          onClick={() => setCreateOpen(true)}
        >
          创建机器人
        </Button>
      </div>

      {/* 机器人卡片网格 */}
      <div className="bot-card-grid">
        {filteredBots.map((bot) => {
          const isOnline = bot.status === 'online'
          const statusText = isOnline ? '已上线' : '训练中'
          const dotColor = isOnline ? 'var(--success)' : 'var(--warning)'
          return (
            <div key={bot.id} className="bot-card" onClick={() => navigate(`/bots/${bot.id}`)}>
              <span className={`bot-card-status badge ${isOnline ? 'badge-success' : 'badge-warning'}`}>
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
                      <div className="more-item more-item-danger" onClick={() => handleMoreAction('删除')}>
                        删除
                      </div>
                    </div>
                  </>
                )}
              </div>
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
                  handleCreateCard()
                }}
              >
                <div className="bot-card-header">
                  <div className="bot-avatar">模</div>
                  <div className="bot-info">
                    <div className="bot-name">从模板创建</div>
                    <div className="bot-meta">使用预制模板进行创建</div>
                  </div>
                </div>
              </div>
              <div
                className="bot-card create-card"
                onClick={(e) => {
                  e.stopPropagation()
                  handleCreateCard()
                }}
              >
                <div className="bot-card-header">
                  <div className="bot-avatar bot-avatar-alt">编</div>
                  <div className="bot-info">
                    <div className="bot-name">从编排创建</div>
                    <div className="bot-meta">从0开始编排创建</div>
                  </div>
                </div>
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
    </div>
  )
}
