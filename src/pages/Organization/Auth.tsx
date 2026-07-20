import { useMemo, useRef, useState } from 'react'
import { Plus, Search, RotateCcw, Pencil, Trash2, Check } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import '../../pages/prototype.css'
import './Auth.css'

/** 是否使用本地 mock 数据。接入真实后端时置为 false 并取消注释下方 fetch 调用。 */
const USE_MOCK = true

// 后端接口契约（mock 阶段暂未启用，接入真实后端时取消注释并替换本地状态）：
// GET    /api/org/auth-users        -> 拉取授权用户列表
// POST   /api/org/auth-users        -> 新增授权用户
// PUT    /api/org/auth-users/{id}   -> 更新授权用户
// DELETE /api/org/auth-users/{id}   -> 删除授权用户

/** 授权用户实体。 */
interface AuthUser {
  id: string
  account: string
  nickname: string
  role: string
}

/** 可选角色（与角色管理页保持一致）。 */
const ROLES: string[] = ['管理员', '团队组长', '普通成员']

/** 授权用户种子数据（mock-first）。 */
const MOCK_AUTH_USERS: AuthUser[] = [
  { id: 'auth-1', account: 'admin@morphix', nickname: '谷一莹', role: '管理员' },
  { id: 'auth-2', account: 'leader@morphix', nickname: '沈墨白', role: '团队组长' },
  { id: 'auth-3', account: 'member01@morphix', nickname: '陈知夏', role: '普通成员' },
  { id: 'auth-4', account: 'member02@morphix', nickname: '林晚舟', role: '普通成员' },
  { id: 'auth-5', account: 'leader02@morphix', nickname: '苏砚清', role: '团队组长' },
]

function genId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`
}

/** 角色 -> 徽标配色（与角色管理页一致）。 */
function roleBadge(role: string): string {
  if (role === '管理员') return 'proto-badge-danger'
  if (role === '团队组长') return 'proto-badge-success'
  return 'proto-badge-info'
}

/**
 * 授权用户管理页（/organization/auth）。
 * mock-first：种子数据 + 本地受控状态，支持按登录账号 / 用户昵称筛选、新增、编辑、删除。
 */
export default function AuthPage() {
  const [users, setUsers] = useState<AuthUser[]>(USE_MOCK ? MOCK_AUTH_USERS : [])

  // 筛选输入（草稿）与已应用筛选条件
  const [accountInput, setAccountInput] = useState('')
  const [nicknameInput, setNicknameInput] = useState('')
  const [appliedAccount, setAppliedAccount] = useState('')
  const [appliedNickname, setAppliedNickname] = useState('')

  // 新增 / 编辑弹窗
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formAccount, setFormAccount] = useState('')
  const [formNickname, setFormNickname] = useState('')
  const [formRole, setFormRole] = useState<string>(ROLES[0])

  // 删除确认弹窗
  const [deleteTarget, setDeleteTarget] = useState<AuthUser | null>(null)

  // 成功提示
  const [notice, setNotice] = useState<string | null>(null)
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showNotice = (msg: string) => {
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    setNotice(msg)
    noticeTimer.current = setTimeout(() => setNotice(null), 2500)
  }

  const visible = useMemo(() => {
    const acc = appliedAccount.trim().toLowerCase()
    const nick = appliedNickname.trim().toLowerCase()
    return users.filter((u) => {
      if (acc && !u.account.toLowerCase().includes(acc)) return false
      if (nick && !u.nickname.toLowerCase().includes(nick)) return false
      return true
    })
  }, [users, appliedAccount, appliedNickname])

  const handleQuery = () => {
    setAppliedAccount(accountInput)
    setAppliedNickname(nicknameInput)
  }

  const handleReset = () => {
    setAccountInput('')
    setNicknameInput('')
    setAppliedAccount('')
    setAppliedNickname('')
  }

  const openCreate = () => {
    setEditingId(null)
    setFormAccount('')
    setFormNickname('')
    setFormRole(ROLES[0])
    setFormOpen(true)
  }

  const openEdit = (u: AuthUser) => {
    setEditingId(u.id)
    setFormAccount(u.account)
    setFormNickname(u.nickname)
    setFormRole(u.role)
    setFormOpen(true)
  }

  const handleSave = () => {
    const account = formAccount.trim()
    const nickname = formNickname.trim()
    const role = formRole
    if (!account || !nickname || !role) return
    if (editingId) {
      setUsers((prev) =>
        prev.map((u) => (u.id === editingId ? { ...u, account, nickname, role } : u))
      )
      showNotice('用户已更新')
    } else {
      const newUser: AuthUser = { id: genId('auth'), account, nickname, role }
      setUsers((prev) => [...prev, newUser])
      showNotice('用户已添加')
    }
    setFormOpen(false)
  }

  const confirmDelete = () => {
    if (!deleteTarget) return
    const account = deleteTarget.account
    setUsers((prev) => prev.filter((u) => u.id !== deleteTarget.id))
    setDeleteTarget(null)
    showNotice(`用户「${account}」已删除`)
  }

  const formValid = formAccount.trim() !== '' && formNickname.trim() !== '' && formRole !== ''

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">授权用户管理</h2>
          <p className="page-subtitle">管理可登录控制台并操作私域资源的成员账号</p>
        </div>
      </div>

      <div className="proto-card">
        {/* 筛选栏 */}
        <div className="auth-filter-bar">
          <div className="auth-filter-field">
            <label className="auth-filter-label">登录账号</label>
            <input
              className="input"
              placeholder="请输入"
              value={accountInput}
              onChange={(e) => setAccountInput(e.target.value)}
            />
          </div>
          <div className="auth-filter-field">
            <label className="auth-filter-label">用户昵称</label>
            <input
              className="input"
              placeholder="请输入"
              value={nicknameInput}
              onChange={(e) => setNicknameInput(e.target.value)}
            />
          </div>
          <div className="auth-filter-actions">
            <Button variant="secondary" size="sm" icon={<RotateCcw size={14} />} onClick={handleReset}>
              重置
            </Button>
            <Button variant="primary" size="sm" icon={<Search size={14} />} onClick={handleQuery}>
              查询
            </Button>
            <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={openCreate}>
              新增
            </Button>
          </div>
        </div>

        {/* 用户表格 */}
        <table className="proto-table">
          <thead>
            <tr>
              <th>登录账号</th>
              <th>用户昵称</th>
              <th>所属角色</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={4} className="auth-empty">
                  <svg viewBox="0 0 200 200" aria-hidden="true">
                    <rect x="50" y="60" width="100" height="80" rx="8" fill="#f1f6fd" stroke="#e0e0dd" strokeWidth="2" />
                    <path d="M70 95h60M70 115h40" stroke="#d0d0cc" strokeWidth="4" strokeLinecap="round" />
                    <circle cx="160" cy="50" r="12" fill="#e9f1fd" opacity="0.6" />
                  </svg>
                  <div>暂无数据</div>
                </td>
              </tr>
            ) : (
              visible.map((u) => (
                <tr key={u.id}>
                  <td>{u.account}</td>
                  <td>{u.nickname}</td>
                  <td>
                    <span className={`proto-badge ${roleBadge(u.role)}`}>{u.role}</span>
                  </td>
                  <td>
                    <div className="auth-row-actions">
                      <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={() => openEdit(u)}>
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 size={14} />}
                        className="auth-action-danger"
                        onClick={() => setDeleteTarget(u)}
                      >
                        删除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {notice && (
          <div className="proto-notice proto-notice-success auth-notice">
            <Check size={14} /> {notice}
          </div>
        )}
      </div>

      {/* 新增 / 编辑弹窗 */}
      <Modal
        open={formOpen}
        title={editingId ? '编辑用户' : '新增用户'}
        onClose={() => setFormOpen(false)}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setFormOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={editingId ? undefined : <Plus size={14} />}
              onClick={handleSave}
              disabled={!formValid}
            >
              确定
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">
            登录账号 <span className="required">*</span>
          </label>
          <input
            className="input"
            placeholder="请输入登录账号"
            value={formAccount}
            onChange={(e) => setFormAccount(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            用户昵称 <span className="required">*</span>
          </label>
          <input
            className="input"
            placeholder="请输入用户昵称"
            value={formNickname}
            onChange={(e) => setFormNickname(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            所属角色 <span className="required">*</span>
          </label>
          <select className="select" value={formRole} onChange={(e) => setFormRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </Modal>

      {/* 删除确认弹窗 */}
      <Modal
        open={deleteTarget !== null}
        title="删除用户"
        onClose={() => setDeleteTarget(null)}
        width={400}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="danger" size="sm" icon={<Trash2 size={14} />} onClick={confirmDelete}>
              删除
            </Button>
          </>
        }
      >
        <p className="auth-confirm-text">确定删除该用户？删除后该账号将无法登录控制台。</p>
      </Modal>
    </div>
  )
}
