import { useMemo, useRef, useState } from 'react'
import { Plus, Search, RotateCcw } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import '../../pages/prototype.css'
import './Roles.css'

/** 是否使用本地 mock 数据。接入真实后端时置为 false 并取消注释下方 fetch 调用。 */
const USE_MOCK = true

// 后端接口契约（mock 阶段暂未启用，接入真实后端时取消注释并替换本地状态）：
// GET    /api/org/roles                   -> 拉取全部角色
// POST   /api/org/roles                   -> 新建角色
// PUT    /api/org/roles/{id}              -> 更新角色
// DELETE /api/org/roles/{id}              -> 删除角色
// GET/PUT /api/org/roles/{id}/permissions -> 角色权限矩阵

/** 角色颜色，与 seed 数据中的徽标配色一一对应。 */
type RoleColor = 'danger' | 'success' | 'info'

/** 角色实体。 */
interface Role {
  id: string
  name: string
  description: string
  color: RoleColor
}

/** 角色颜色 -> 新增/编辑弹窗下拉项。 */
const COLOR_OPTIONS: { value: RoleColor; label: string }[] = [
  { value: 'danger', label: '管理员红' },
  { value: 'success', label: '团队组长绿' },
  { value: 'info', label: '普通成员蓝' },
]

/** 角色颜色 -> 标签底色（与 prototype 原型像素级一致）。 */
const COLOR_STYLE: Record<RoleColor, { background: string; color: string }> = {
  danger: { background: '#f9e8e8', color: '#d76b6b' },
  success: { background: '#eef6ea', color: '#5a8f48' },
  info: { background: '#eaf2f9', color: '#4a7ba8' },
}

/** 权限模块清单（编辑权限弹窗使用）。 */
const PERMISSION_MODULES = ['客户管理', '运营任务', '渠道管理', '组织管理', '资源管理'] as const

/** 每个角色的权限勾选状态，外层键为 role id。 */
type PermissionMap = Record<string, Record<string, boolean>>

/** 种子角色：与 prototype 原型的 3 行完全一致。 */
const MOCK_ROLES: Role[] = [
  { id: 'role-admin', name: '管理员', description: '管理员', color: 'danger' },
  { id: 'role-lead', name: '团队组长', description: '团队组长', color: 'success' },
  { id: 'role-member', name: '普通成员', description: '普通成员', color: 'info' },
]

/** 依据颜色给出预置权限（管理员全开，组长/成员部分勾选）。 */
function seedPerms(role: Role): Record<string, boolean> {
  const base: Record<string, boolean> = {}
  PERMISSION_MODULES.forEach((m) => {
    base[m] = false
  })
  if (role.color === 'danger') {
    PERMISSION_MODULES.forEach((m) => {
      base[m] = true
    })
  } else if (role.color === 'success') {
    ;['客户管理', '运营任务', '渠道管理'].forEach((m) => {
      base[m] = true
    })
  } else {
    base['客户管理'] = true
    base['组织管理'] = true
  }
  return base
}

/** 新建角色的默认权限（勾选前两个模块）。 */
function defaultPerms(): Record<string, boolean> {
  const base: Record<string, boolean> = {}
  PERMISSION_MODULES.forEach((m) => {
    base[m] = false
  })
  base[PERMISSION_MODULES[0]] = true
  base[PERMISSION_MODULES[1]] = true
  return base
}

/** 由角色列表构造初始权限映射。 */
function buildInitialPerms(roles: Role[]): PermissionMap {
  const map: PermissionMap = {}
  roles.forEach((r) => {
    map[r.id] = seedPerms(r)
  })
  return map
}

const INITIAL_PERMS: PermissionMap = buildInitialPerms(MOCK_ROLES)

/** 生成唯一 id（mock 阶段使用，不进入后端契约）。 */
function genId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`
}

/**
 * 角色权限管理页（/organization/roles）。
 * mock-first：种子数据 + 本地状态，支持按名称筛选、新增/编辑角色、编辑角色权限矩阵、删除角色。
 */
export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>(USE_MOCK ? MOCK_ROLES : [])
  const [perms, setPerms] = useState<PermissionMap>(INITIAL_PERMS)

  // 筛选
  const [keyword, setKeyword] = useState('')
  const [query, setQuery] = useState('')

  // 新增/编辑角色弹窗
  const [roleModalOpen, setRoleModalOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formColor, setFormColor] = useState<RoleColor>('info')

  // 编辑权限弹窗
  const [permModalOpen, setPermModalOpen] = useState(false)
  const [permRole, setPermRole] = useState<Role | null>(null)
  const [permDraft, setPermDraft] = useState<Record<string, boolean>>(defaultPerms)

  // 删除确认弹窗
  const [deleteRole, setDeleteRole] = useState<Role | null>(null)

  // 成功提示
  const [notice, setNotice] = useState('')
  const noticeTimer = useRef<number | undefined>(undefined)

  const showNotice = (msg: string) => {
    setNotice(msg)
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(''), 2000)
  }

  // 按已应用的查询关键字过滤（name 包含匹配）。
  const filtered = useMemo(() => {
    const q = query.trim()
    if (!q) return roles
    return roles.filter((r) => r.name.includes(q))
  }, [roles, query])

  const handleQuery = () => setQuery(keyword)
  const handleReset = () => {
    setKeyword('')
    setQuery('')
  }

  // ---- 新增 / 编辑角色 ----
  const openCreate = () => {
    setEditingRole(null)
    setFormName('')
    setFormDesc('')
    setFormColor('info')
    setRoleModalOpen(true)
  }

  const openEditRole = (role: Role) => {
    setEditingRole(role)
    setFormName(role.name)
    setFormDesc(role.description)
    setFormColor(role.color)
    setRoleModalOpen(true)
  }

  const saveRole = () => {
    const name = formName.trim()
    if (!name) return
    if (editingRole) {
      const id = editingRole.id
      setRoles((prev) =>
        prev.map((r) =>
          r.id === id ? { ...r, name, description: formDesc.trim(), color: formColor } : r
        )
      )
      showNotice('角色已更新')
    } else {
      const id = genId('role')
      const newRole: Role = { id, name, description: formDesc.trim(), color: formColor }
      setRoles((prev) => [newRole, ...prev])
      setPerms((prev) => ({ ...prev, [id]: defaultPerms() }))
      showNotice('角色已创建')
    }
    setRoleModalOpen(false)
  }

  // ---- 编辑权限 ----
  const openPerm = (role: Role) => {
    setPermRole(role)
    setPermDraft({ ...(perms[role.id] ?? defaultPerms()) })
    setPermModalOpen(true)
  }

  const togglePerm = (module: string) => {
    setPermDraft((prev) => ({ ...prev, [module]: !prev[module] }))
  }

  const savePerm = () => {
    if (!permRole) return
    setPerms((prev) => ({ ...prev, [permRole.id]: permDraft }))
    setPermModalOpen(false)
    showNotice('权限已保存')
  }

  // ---- 删除 ----
  const confirmDelete = () => {
    if (!deleteRole) return
    const id = deleteRole.id
    setRoles((prev) => prev.filter((r) => r.id !== id))
    setPerms((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    showNotice('角色已删除')
    setDeleteRole(null)
  }

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">角色权限管理</h2>
          <p className="page-subtitle">配置团队成员的角色与对应权限范围</p>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="proto-card roles-filter-bar">
        <input
          className="input roles-search"
          placeholder="角色"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleQuery()
          }}
        />
        <div className="roles-actions">
          <Button variant="secondary" size="sm" icon={<RotateCcw size={14} />} onClick={handleReset}>
            重置
          </Button>
          <Button variant="primary" size="sm" icon={<Search size={14} />} onClick={handleQuery}>
            查询
          </Button>
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={openCreate}>
            新增角色
          </Button>
        </div>
      </div>

      {/* 角色表格 */}
      <div className="proto-card">
        {filtered.length === 0 ? (
          <div className="roles-empty">
            <p>暂无角色，点击右上角「新增角色」开始创建。</p>
          </div>
        ) : (
          <table className="proto-table">
            <thead>
              <tr>
                <th>角色</th>
                <th>角色描述</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((role) => (
                <tr key={role.id}>
                  <td>
                    <span className="role-badge" style={COLOR_STYLE[role.color]}>
                      {role.name}
                    </span>
                  </td>
                  <td>{role.description}</td>
                  <td>
                    <div className="roles-row-actions">
                      <Button variant="ghost" size="sm" onClick={() => openEditRole(role)}>
                        编辑角色
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openPerm(role)}>
                        编辑权限
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="btn-danger-text"
                        onClick={() => setDeleteRole(role)}
                      >
                        删除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {notice && <div className="proto-notice proto-notice-success">{notice}</div>}

      {/* 新增 / 编辑角色 */}
      <Modal
        open={roleModalOpen}
        title={editingRole ? '编辑角色' : '新增角色'}
        onClose={() => setRoleModalOpen(false)}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setRoleModalOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={saveRole}
              disabled={!formName.trim()}
            >
              保存
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">
            角色名称 <span className="required">*</span>
          </label>
          <input
            className="input"
            value={formName}
            placeholder="如：管理员"
            onChange={(e) => setFormName(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">角色描述</label>
          <input
            className="input"
            value={formDesc}
            placeholder="如：拥有全部权限"
            onChange={(e) => setFormDesc(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">角色颜色</label>
          <select
            className="select"
            value={formColor}
            onChange={(e) => setFormColor(e.target.value as RoleColor)}
          >
            {COLOR_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </Modal>

      {/* 编辑权限 */}
      <Modal
        open={permModalOpen && permRole !== null}
        title={`编辑权限 · ${permRole?.name ?? ''}`}
        onClose={() => setPermModalOpen(false)}
        width={520}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setPermModalOpen(false)}>
              取消
            </Button>
            <Button variant="primary" size="sm" onClick={savePerm}>
              保存
            </Button>
          </>
        }
      >
        <p className="roles-perm-tip">为该角色勾选可访问的权限模块：</p>
        <div className="roles-perm-matrix">
          {PERMISSION_MODULES.map((module) => (
            <label key={module} className="roles-perm-item">
              <input
                type="checkbox"
                checked={permDraft[module] ?? false}
                onChange={() => togglePerm(module)}
              />
              <span>{module}</span>
            </label>
          ))}
        </div>
      </Modal>

      {/* 删除确认 */}
      <Modal
        open={deleteRole !== null}
        title="删除角色"
        onClose={() => setDeleteRole(null)}
        width={400}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setDeleteRole(null)}>
              取消
            </Button>
            <Button variant="danger" size="sm" onClick={confirmDelete}>
              删除
            </Button>
          </>
        }
      >
        <p className="roles-delete-text">确定删除角色「{deleteRole?.name}」？</p>
      </Modal>
    </div>
  )
}
