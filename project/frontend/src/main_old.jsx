import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity,
  BarChart3,
  Bot,
  BrainCircuit,
  ChevronDown,
  CircleCheck,
  Clock3,
  Database,
  GitBranch,
  Home,
  MessageCircle,
  Play,
  Plus,
  Search,
  Send,
  X,
  Settings,
  ShieldCheck,
  Sparkles,
  Tags,
  Users,
  Workflow,
  Zap,
} from 'lucide-react'
import './styles.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const navItems = [
  { id: 'home', label: '首页', icon: Home },
  { id: 'bots', label: 'AI机器人', icon: Bot },
  { id: 'sessions', label: '渠道会话', icon: MessageCircle },
  { id: 'customers', label: '客户管理', icon: Users },
  { id: 'sop', label: '运营管理', icon: Workflow },
  { id: 'resources', label: '资源管理', icon: Database },
  { id: 'data', label: '数据面板', icon: BarChart3 },
  { id: 'llm', label: 'LLM配置', icon: BrainCircuit },
]

const fallbackData = {
  stats: {
    activeProjects: 4,
    channelAccounts: 28,
    aiSessions: 1264,
    conversionRate: '18.7%',
  },
  bots: [
    { id: 'bot-1', name: '美妆销售顾问', project: 'GlowLab', status: 'online', workflow: '销售接待主流程', tone: '亲切专业', score: 92 },
    { id: 'bot-2', name: '企微售后助手', project: 'Morphix Demo', status: 'training', workflow: '售后问题处理', tone: '耐心清晰', score: 81 },
    { id: 'bot-3', name: 'WhatsApp 成交助理', project: 'Global Fit', status: 'online', workflow: '海外询盘跟进', tone: '国际化', score: 88 },
  ],
  sessions: [
    { id: 's-1', name: '张先生', channel: '企业微信', bot: '美妆销售顾问', state: 'AI托管', intent: '价格咨询', last: '标准版支持多少个账号？', time: '2分钟前' },
    { id: 's-2', name: 'Alicia', channel: 'WhatsApp', bot: 'WhatsApp 成交助理', state: '人工接管', intent: '预约演示', last: 'Can we schedule a demo?', time: '8分钟前' },
    { id: 's-3', name: '宝妈护肤交流群', channel: '微信群', bot: '群聊识别 Agent', state: 'AI托管', intent: '群内意向', last: '有人问优惠活动', time: '14分钟前' },
  ],
  customers: [
    { id: 'c-1', name: '张先生', level: '高意向', tags: ['价格咨询', '预约演示'], stage: '需求挖掘', owner: '企微-华东01' },
    { id: 'c-2', name: 'Alicia', level: '中意向', tags: ['海外客户', 'WhatsApp'], stage: '产品推荐', owner: 'WA-Biz-02' },
    { id: 'c-3', name: '林女士', level: '高意向', tags: ['敏感肌', '复购'], stage: '逼单促销', owner: '微信-美妆03' },
  ],
  workflows: [
    { id: 'w-1', name: '销售接待主流程', nodes: 9, status: '已发布', updatedAt: '今天 10:24' },
    { id: 'w-2', name: '知识库严格问答', nodes: 6, status: '草稿', updatedAt: '昨天 19:02' },
    { id: 'w-3', name: '群聊意向转私聊', nodes: 11, status: '灰度中', updatedAt: '周一 15:40' },
  ],
}

async function fetchDashboard() {
  try {
    const response = await fetch(`${API_BASE}/dashboard`)
    if (!response.ok) throw new Error('bad response')
    return await response.json()
  } catch {
    return fallbackData
  }
}

async function postJson(path, payload) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error('bad response')
    return await response.json()
  } catch {
    return null
  }
}

async function patchJson(path, payload) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error('bad response')
    return await response.json()
  } catch {
    return null
  }
}

function Badge({ children, tone = 'blue' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

function Sidebar({ active, onChange }) {
  return (
    <aside className="sidebar">
      <div className="brand-card">
        <div className="brand-mark">M</div>
        <div>
          <div className="brand-title">Morphix</div>
          <div className="brand-subtitle">AI运营协同平台</div>
        </div>
      </div>
      <div className="project-switcher">
        <div>
          <span>当前项目</span>
          <strong>GlowLab 私域增长</strong>
        </div>
        <ChevronDown size={16} />
      </div>
      <nav className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <button key={item.id} className={`nav-item ${active === item.id ? 'active' : ''}`} onClick={() => onChange(item.id)}>
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          )
        })}
      </nav>
      <div className="side-status">
        <ShieldCheck size={18} />
        <div>
          <strong>治理模式开启</strong>
          <span>发布、审计、回滚可追踪</span>
        </div>
      </div>
    </aside>
  )
}

function Header({ active }) {
  const title = navItems.find((item) => item.id === active)?.label || '首页'
  const [notice, setNotice] = useState('')
  const flash = (text) => {
    setNotice(text)
    window.setTimeout(() => setNotice(''), 1800)
  }
  return (
    <header className="topbar">
      <div>
        <div className="eyebrow"><Sparkles size={14} /> 多项目 / 多渠道 / 多 Agent</div>
        <h1>{title}</h1>
      </div>
      <div className="top-actions">
        <div className="search-box"><Search size={16} /><input placeholder="搜索客户、会话、机器人" /></div>
        <button className="btn ghost" onClick={() => flash('项目设置面板将在下一阶段接入权限与审计配置')}><Settings size={16} /> 设置</button>
        <button className="btn primary" onClick={() => flash('已进入新建入口：可创建机器人、SOP 或渠道账号')}><Plus size={16} /> 新建</button>
      </div>
      {notice && <div className="toast">{notice}</div>}
    </header>
  )
}

function HomePage({ data }) {
  const cards = [
    ['活跃项目', data.stats.activeProjects, '项目独立配置机器人与知识库', GitBranch],
    ['渠道账号', data.stats.channelAccounts, '微信、企微、WhatsApp 统一接入', Zap],
    ['AI托管会话', data.stats.aiSessions, '今日自动接待与跟进', MessageCircle],
    ['成交转化率', data.stats.conversionRate, 'SOP 触达后的综合转化', Activity],
  ]
  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <Badge tone="gold">MVP主链路</Badge>
          <h2>用可配置机器人和工作流，把私域销售执行流程产品化。</h2>
          <p>覆盖项目配置、机器人训练、渠道托管、客户跟进、SOP 自动化与数据监控，优先打通运营可观察、可接管、可排障闭环。</p>
        </div>
        <div className="hero-flow">
          {['用户输入', '需求分析', '知识检索', 'AI生成', '渠道发送'].map((item, index) => <span key={item}>{index + 1}. {item}</span>)}
        </div>
      </section>
      <section className="metric-grid">
        {cards.map(([label, value, desc, Icon]) => (
          <article className="metric-card" key={label}>
            <Icon size={20} />
            <strong>{value}</strong>
            <span>{label}</span>
            <p>{desc}</p>
          </article>
        ))}
      </section>
      <section className="card wide">
        <div className="card-head"><h3>运行态雷达</h3><Badge>实时</Badge></div>
        <div className="runtime-strip">
          {['意图识别稳定', '知识命中率 86%', '人工接管 12 单', '设备在线 24/28'].map((item) => <div key={item}><CircleCheck size={16} />{item}</div>)}
        </div>
      </section>
    </div>
  )
}

function BotsPage({ data }) {
  const [bots, setBots] = useState(data.bots)
  const [modalOpen, setModalOpen] = useState(false)
  const [toast, setToast] = useState('')
  useEffect(() => setBots(data.bots), [data.bots])
  const trainBot = async (bot) => {
    await postJson(`/bots/${bot.id}/train`, {})
    setBots((items) => items.map((item) => item.id === bot.id ? { ...item, status: 'online', score: Math.min((item.score || 70) + 8, 99) } : item))
    setToast(`${bot.name} 训练完成，已切换在线`)
    window.setTimeout(() => setToast(''), 1800)
  }
  const addBot = async (payload) => {
    const created = await postJson('/bots', payload)
    setBots((items) => [...items, created || { id: `local-${Date.now()}`, status: 'training', score: 76, ...payload }])
    setModalOpen(false)
  }
  return (
    <>
      {toast && <div className="toast floating">{toast}</div>}
      <div className="card-head page-action-head"><h3>机器人训练台</h3><button className="btn primary" onClick={() => setModalOpen(true)}><Plus size={16} /> 创建 Bot</button></div>
      <div className="content-grid three">
        {bots.map((bot) => (
          <article className="card bot-card" key={bot.id}>
            <div className="bot-avatar"><Bot size={24} /></div>
            <h3>{bot.name}</h3>
            <p>{bot.project} · {bot.workflow}</p>
            <div className="meta-row"><Badge tone={bot.status === 'online' ? 'green' : 'gold'}>{bot.status === 'online' ? '在线' : '训练中'}</Badge><span>{bot.tone}</span></div>
            <div className="score"><span style={{ width: `${bot.score}%` }} /></div>
            <button className="btn full" onClick={() => trainBot(bot)}><Play size={16} /> 训练并上线</button>
          </article>
        ))}
      </div>
      {modalOpen && <BotModal onClose={() => setModalOpen(false)} onSave={addBot} />}
    </>
  )
}

function BotModal({ onClose, onSave }) {
  const [form, setForm] = useState({ name: '新人销售训练助手', project: 'GlowLab', workflow: '销售接待主流程', tone: '专业、有边界感', trainingPrompt: '识别客户意图，引用知识库，无法确认时转人工。' })
  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))
  return (
    <div className="modal-mask">
      <section className="modal-card">
        <div className="drawer-head"><div><Badge>Bot 创建</Badge><h3>训练一个新机器人</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>
        <div className="form-grid">
          <label>Bot 名称<input value={form.name} onChange={(event) => update('name', event.target.value)} /></label>
          <label>所属项目<input value={form.project} onChange={(event) => update('project', event.target.value)} /></label>
          <label>绑定工作流<input value={form.workflow} onChange={(event) => update('workflow', event.target.value)} /></label>
          <label>回复风格<input value={form.tone} onChange={(event) => update('tone', event.target.value)} /></label>
        </div>
        <label>训练提示词<textarea value={form.trainingPrompt} onChange={(event) => update('trainingPrompt', event.target.value)} /></label>
        <button className="btn primary full" onClick={() => onSave(form)}>创建并进入训练</button>
      </section>
    </div>
  )
}

function SessionsPage({ data }) {
  const [active, setActive] = useState(data.sessions[0]?.id)
  const [handoffStatus, setHandoffStatus] = useState({})
  const [toast, setToast] = useState('')
  const [messagePage, setMessagePage] = useState(1)
  const current = data.sessions.find((item) => item.id === active) || data.sessions[0]
  const stateLabel = handoffStatus[current?.id] || current?.state
  const visibleMessages = [
    ['customer', current?.last],
    ['ai', `已识别为「${current?.intent}」，正在结合知识库与 SOP 阶段生成回复。`],
    ['system', 'Workflow Run: 需求分析 -> 知识检索 -> 表达控制 -> 渠道发送'],
    ...(messagePage > 1 ? [['customer', '客户补充：如果今天能安排演示，我可以拉老板一起看。'], ['ai', '建议动作：发送演示预约链接，并同步高意向标签。']] : []),
  ]
  const requestHandoff = async () => {
    if (!current) return
    await postJson(`/conversations/${current.id}/handoff`, { operator: '当前运营', reason: 'console_takeover' })
    setHandoffStatus((prev) => ({ ...prev, [current.id]: '人工接管' }))
    setToast(`已接管 ${current.name} 的会话`)
    window.setTimeout(() => setToast(''), 1800)
  }
  return (
    <div className="session-layout">
      {toast && <div className="toast floating">{toast}</div>}
      <section className="card session-list">
        <div className="card-head"><h3>会话队列</h3><Badge>{data.sessions.length} 条</Badge></div>
        {data.sessions.map((session) => (
          <button key={session.id} className={`session-item ${active === session.id ? 'active' : ''}`} onClick={() => setActive(session.id)}>
            <strong>{session.name}</strong><span>{session.time}</span><p>{session.last}</p><Badge tone={session.state === 'AI托管' ? 'green' : 'gold'}>{session.state}</Badge>
          </button>
        ))}
      </section>
      <section className="card chat-panel">
        <div className="card-head"><h3>{current?.name}</h3><Badge tone="green">{current?.channel}</Badge></div>
        <div className="chat-stream">
          <button className="load-more" onClick={() => setMessagePage((page) => page + 1)}>加载更早消息</button>
          {visibleMessages.map(([type, text], index) => <div key={`${type}-${index}`} className={`bubble ${type}`}>{text}</div>)}
        </div>
        <div className="composer"><input placeholder="人工接管后可输入回复" /><button><Send size={16} /></button></div>
      </section>
      <section className="card inspector">
        <div className="card-head"><h3>运行态</h3><Badge tone="blue">可接管</Badge></div>
        <dl>
          <dt>当前机器人</dt><dd>{current?.bot}</dd>
          <dt>会话状态</dt><dd>{stateLabel}</dd>
          <dt>客户意图</dt><dd>{current?.intent}</dd>
          <dt>下一动作</dt><dd>推荐产品 + 预约演示</dd>
        </dl>
        <button className="btn primary full" onClick={requestHandoff}>发起人工接管</button>
        <button className="btn full" onClick={() => setToast('节点轨迹：需求分析 -> 知识检索 -> 表达控制 -> 渠道发送')}>查看节点轨迹</button>
      </section>
    </div>
  )
}

function CustomersPage({ data }) {
  const [activeCustomer, setActiveCustomer] = useState(null)
  const [tagOpen, setTagOpen] = useState(false)
  return (
    <>
      <section className="card table-card">
        <div className="card-head"><h3>客户档案</h3><button className="btn" onClick={() => setTagOpen(true)}><Tags size={16} /> 标签管理</button></div>
        <table>
          <thead><tr><th>客户</th><th>意向等级</th><th>标签</th><th>阶段</th><th>归属账号</th><th>操作</th></tr></thead>
          <tbody>{data.customers.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.level}</td><td>{item.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</td><td>{item.stage}</td><td>{item.owner}</td><td><button className="link-btn" onClick={() => setActiveCustomer(item)}>查看详情</button></td></tr>)}</tbody>
        </table>
      </section>
      {activeCustomer && <CustomerDrawer customer={activeCustomer} onClose={() => setActiveCustomer(null)} />}
      {tagOpen && <TagModal data={data} onClose={() => setTagOpen(false)} />}
    </>
  )
}

function TagModal({ data, onClose }) {
  const [tags, setTags] = useState(data.tags || [{ id: 'tag-1', name: '高意向', color: 'green', rule: '最近 7 天主动咨询价格或预约' }])
  const [form, setForm] = useState({ name: '复购潜力', color: 'green', rule: '30 天内多次咨询同类商品' })
  const save = async () => {
    const created = await postJson('/customer-tags', form)
    setTags((items) => [...items, created || { id: `tag-${Date.now()}`, ...form }])
  }
  return (
    <div className="modal-mask">
      <section className="modal-card wide-modal">
        <div className="drawer-head"><div><Badge tone="green">标签管理</Badge><h3>客户标签规则</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>
        <div className="tag-list">{tags.map((tag) => <div key={tag.id}><Badge tone={tag.color}>{tag.name}</Badge><span>{tag.rule}</span></div>)}</div>
        <div className="form-grid">
          <label>标签名<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label>颜色<select value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })}><option value="blue">蓝色</option><option value="green">绿色</option><option value="gold">金色</option></select></label>
        </div>
        <label>自动打标规则<textarea value={form.rule} onChange={(event) => setForm({ ...form, rule: event.target.value })} /></label>
        <button className="btn primary full" onClick={save}>保存标签</button>
      </section>
    </div>
  )
}

function ResourcesPage({ data }) {
  const [channels, setChannels] = useState(data.channels || [
    { id: 'ch-1', channel: '企业微信', accountName: '企微-华东01', status: 'online', boundBot: '美妆销售顾问', dailyQuota: 600 },
    { id: 'ch-2', channel: 'WhatsApp', accountName: 'WA-Biz-02', status: 'online', boundBot: 'WhatsApp 成交助理', dailyQuota: 300 },
  ])
  const [modalOpen, setModalOpen] = useState(false)
  useEffect(() => { if (data.channels) setChannels(data.channels) }, [data.channels])
  const addChannel = async (payload) => {
    const created = await postJson('/channel-accounts', payload)
    setChannels((items) => [...items, created || { id: `ch-${Date.now()}`, status: 'online', ...payload }])
    setModalOpen(false)
  }
  return (
    <>
      <div className="card-head page-action-head"><h3>渠道账号托管</h3><button className="btn primary" onClick={() => setModalOpen(true)}><Plus size={16} /> 接入账号</button></div>
      <div className="content-grid three">
        {channels.map((channel) => <article className="card channel-card" key={channel.id}><Zap size={22} /><h3>{channel.accountName}</h3><p>{channel.channel} · 绑定 {channel.boundBot}</p><Badge tone={channel.status === 'online' ? 'green' : 'gold'}>{channel.status === 'online' ? '在线托管' : '需处理'}</Badge><div className="quota"><span style={{ width: `${Math.min(channel.dailyQuota / 8, 100)}%` }} /></div><small>日触达额度 {channel.dailyQuota}</small></article>)}
      </div>
      {modalOpen && <ChannelModal onClose={() => setModalOpen(false)} onSave={addChannel} />}
    </>
  )
}

function ChannelModal({ onClose, onSave }) {
  const [form, setForm] = useState({ channel: '企业微信', accountName: '企微-华南02', boundBot: '美妆销售顾问', dailyQuota: 300 })
  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: key === 'dailyQuota' ? Number(value) : value }))
  return (
    <div className="modal-mask"><section className="modal-card"><div className="drawer-head"><div><Badge>渠道托管</Badge><h3>接入新账号</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div><div className="form-grid"><label>渠道<select value={form.channel} onChange={(event) => update('channel', event.target.value)}><option>企业微信</option><option>微信</option><option>WhatsApp</option><option>微信群</option></select></label><label>账号名称<input value={form.accountName} onChange={(event) => update('accountName', event.target.value)} /></label><label>绑定 Bot<input value={form.boundBot} onChange={(event) => update('boundBot', event.target.value)} /></label><label>日触达额度<input type="number" value={form.dailyQuota} onChange={(event) => update('dailyQuota', event.target.value)} /></label></div><button className="btn primary full" onClick={() => onSave(form)}>保存并托管</button></section></div>
  )
}

function CustomerDrawer({ customer, onClose }) {
  return (
    <div className="drawer-mask" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-head"><div><Badge tone="green">客户详情</Badge><h3>{customer.name}</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>
        <div className="profile-card"><strong>{customer.level}</strong><span>{customer.stage}</span><p>AI 总结：客户近期互动频繁，关注价格、部署周期和演示安排，建议由资深销售在 24 小时内跟进。</p></div>
        <div className="drawer-section"><h4>客户标签</h4><div>{customer.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div></div>
        <div className="drawer-section"><h4>沟通记录</h4><p>最近一次沟通提到预算审批和演示排期，可使用 SOP「高意向预约演示」继续推进。</p></div>
        <button className="btn primary full">生成跟进建议</button>
      </aside>
    </div>
  )
}

function SopPage({ data }) {
  const [modalOpen, setModalOpen] = useState(false)
  const [activeWorkflow, setActiveWorkflow] = useState(null)
  return (
    <>
      <div className="card-head page-action-head"><h3>SOP 工作流</h3><button className="btn primary" onClick={() => setModalOpen(true)}><Plus size={16} /> 创建 SOP</button></div>
      <div className="content-grid two">
        {data.workflows.map((workflow) => (
          <article className="card workflow-card" key={workflow.id}>
            <div className="card-head"><h3>{workflow.name}</h3><Badge tone="gold">{workflow.status}</Badge></div>
            <div className="workflow-canvas-mini">
              {['触发', '筛选', '生成', '发送'].map((node) => <span key={node}>{node}</span>)}
            </div>
            <p>{workflow.nodes} 个节点 · 更新于 {workflow.updatedAt}</p>
            <button className="btn full" onClick={() => setActiveWorkflow(workflow)}><GitBranch size={16} /> 打开编排</button>
          </article>
        ))}
      </div>
      {modalOpen && <SopModal onClose={() => setModalOpen(false)} />}
      {activeWorkflow && <WorkflowDrawer workflow={activeWorkflow} onClose={() => setActiveWorkflow(null)} />}
    </>
  )
}

function SopModal({ onClose }) {
  const [saved, setSaved] = useState(false)
  const save = async () => {
    await postJson('/sops', { name: '高意向预约演示', trigger: '客户标签=高意向' })
    setSaved(true)
    window.setTimeout(onClose, 900)
  }
  return (
    <div className="modal-mask">
      <section className="modal-card">
        <div className="drawer-head"><div><Badge tone="gold">新建 SOP</Badge><h3>创建运营任务</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>
        <label>任务名称<input defaultValue="高意向预约演示" /></label>
        <label>触发规则<input defaultValue="客户标签包含：高意向、预约演示" /></label>
        <label>发送内容<textarea defaultValue="您好，我帮您约一个 20 分钟产品演示，今天下午或明天上午哪个时间方便？" /></label>
        <button className="btn primary full" onClick={save}>{saved ? '已保存' : '保存并启用'}</button>
      </section>
    </div>
  )
}

function WorkflowDrawer({ workflow, onClose }) {
  const defaultNodes = ['开始触发', '客户筛选', '知识检索', 'AI 生成话术', '渠道发送', '标签沉淀'].map((label, index) => ({ id: `wn-${index + 1}`, label, nodeType: index === 0 ? 'trigger' : 'action', config: { enabled: true } }))
  const [nodes, setNodes] = useState(defaultNodes)
  const [activeNode, setActiveNode] = useState(defaultNodes[0])
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    fetch(`${API_BASE}/workflows/${workflow.id}`).then((response) => response.ok ? response.json() : null).then((detail) => {
      if (detail?.definition?.length) {
        setNodes(detail.definition)
        setActiveNode(detail.definition[0])
      }
    }).catch(() => {})
  }, [workflow.id])
  const saveNode = async () => {
    await patchJson(`/workflows/${workflow.id}/nodes/${activeNode.id}`, activeNode)
    setNodes((items) => items.map((item) => item.id === activeNode.id ? activeNode : item))
    setSaved(true)
    window.setTimeout(() => setSaved(false), 1200)
  }
  return (
    <div className="drawer-mask" onClick={onClose}>
      <aside className="drawer wide-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-head"><div><Badge>工作流画布</Badge><h3>{workflow.name}</h3></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>
        <div className="workflow-editor">
          <div className="canvas-board">
            {nodes.map((node, index) => <button key={node.id} className={`canvas-node ${activeNode?.id === node.id ? 'selected' : ''}`} onClick={() => setActiveNode(node)}><span>{index + 1}</span>{node.label}</button>)}
          </div>
          <section className="node-panel">
            <h4>节点编辑</h4>
            <label>节点名称<input value={activeNode?.label || ''} onChange={(event) => setActiveNode({ ...activeNode, label: event.target.value })} /></label>
            <label>节点类型<select value={activeNode?.nodeType || 'action'} onChange={(event) => setActiveNode({ ...activeNode, nodeType: event.target.value })}><option value="trigger">触发</option><option value="condition">条件</option><option value="action">动作</option><option value="output">输出</option></select></label>
            <label>配置 JSON<textarea value={JSON.stringify(activeNode?.config || {}, null, 2)} onChange={(event) => { try { setActiveNode({ ...activeNode, config: JSON.parse(event.target.value || '{}') }) } catch { setActiveNode({ ...activeNode, config: { raw: event.target.value } }) } }} /></label>
            <button className="btn primary full" onClick={saveNode}>{saved ? '已保存' : '保存节点'}</button>
          </section>
        </div>
        <div className="runtime-strip"><div><CircleCheck size={16} /> 校验通过</div><div><CircleCheck size={16} /> 可发布</div><div><CircleCheck size={16} /> 审计开启</div></div>
      </aside>
    </div>
  )
}

function DataPage({ data }) {
  return (
    <div className="analytics-grid">
      <section className="card chart-card"><h3>渠道转化趋势</h3><div className="bars">{[62, 78, 48, 86, 71, 93, 68].map((h, i) => <span key={i} style={{ height: `${h}%` }} />)}</div></section>
      <section className="card"><h3>Agent 贡献</h3><div className="agent-list">{['需求分析 Agent', '知识检索模块', '表达控制模块', '标签维护 Agent'].map((item, index) => <div key={item}><span>{item}</span><strong>{94 - index * 7}%</strong></div>)}</div></section>
    </div>
  )
}

function PlaceholderPage({ title }) {
  return <section className="card placeholder"><Clock3 size={32} /><h3>{title} 已接入导航</h3><p>MVP 后续会按 PRD 继续扩展完整配置、权限、审计与发布能力。</p></section>
}

function App() {
  const [active, setActive] = useState('home')
  const [data, setData] = useState(fallbackData)

  useEffect(() => {
    fetchDashboard().then(setData)
  }, [])

  const page = useMemo(() => {
    if (active === 'home') return <HomePage data={data} />
    if (active === 'bots') return <BotsPage data={data} />
    if (active === 'sessions') return <SessionsPage data={data} />
    if (active === 'customers') return <CustomersPage data={data} />
    if (active === 'sop') return <SopPage data={data} />
    if (active === 'resources') return <ResourcesPage data={data} />
    if (active === 'data') return <DataPage data={data} />
    return <PlaceholderPage title={navItems.find((item) => item.id === active)?.label} />
  }, [active, data])

  return (
    <div className="app-shell">
      <Sidebar active={active} onChange={setActive} />
      <main className="main-shell">
        <Header active={active} />
        <div className="page-wrap">{page}</div>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
