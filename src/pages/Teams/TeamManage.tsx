/** 团队管理页：基础信息编辑 + 删除 + 成员管理。 */

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Plus } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import type { TeamDTO, TeamMemberDTO } from '../../types/channels'
import AddMemberModal from './shared/AddMemberModal'
import { toast, errText } from '../../utils/toast'
import './Teams.css'

export default function TeamManagePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [team, setTeam] = useState<TeamDTO | null>(null)
  const [teams, setTeams] = useState<TeamDTO[]>([])
  const [members, setMembers] = useState<TeamMemberDTO[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState<'basic' | 'members'>('basic')
  const [memberModalOpen, setMemberModalOpen] = useState(false)

  const loadAll = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [teamsRes, membersRes] = await Promise.all([
        channelsApi.listTeams(),
        channelsApi.listTeamMembers(id),
      ])
      setTeams(teamsRes)
      setMembers(membersRes)
      const t = teamsRes.find((x) => x.id === id) ?? null
      setTeam(t)
      if (t) {
        setName(t.name)
        setDescription(t.description)
      }
    } catch (e) {
      toast(`加载失败：${errText(e)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const handleUpdate = async () => {
    if (!id || !team) return
    const trimmed = name.trim()
    if (!trimmed) {
      toast('团队名称不能为空')
      return
    }
    setSaving(true)
    try {
      const payload = {
        name: trimmed,
        description: description.trim(),
      }
      await channelsApi.updateTeam(id, payload)
      toast('团队信息已更新')
      setTeam((prev) => (prev ? { ...prev, ...payload } : prev))
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !team) return
    if (teams.length <= 1) {
      toast('当前团队为最后一个团队，无法删除')
      return
    }
    try {
      await channelsApi.deleteTeam(id)
      toast('团队已删除')
      navigate('/channels/accounts')
    } catch (e) {
      toast(`删除失败：${errText(e)}`)
    }
  }

  const handleAddMembers = async (userIds: string[]) => {
    if (!id) return
    try {
      const res = await channelsApi.addTeamMembers(id, userIds)
      toast(`已添加 ${res.added} 位成员`)
      setMembers((prev) => [...prev, ...res.members])
      setMemberModalOpen(false)
    } catch (e) {
      toast(`添加失败：${errText(e)}`)
    }
  }

  const isLastTeam = teams.length <= 1

  return (
    <div className="team-page">
      <div className="team-page-header">
        <button className="team-back" onClick={() => navigate(-1)}>
          <ArrowLeft size={18} />
          <span>返回</span>
        </button>
      </div>

      <div className="team-page-title">管理：{team?.name ?? ''}</div>

      <div className="team-tabs">
        <button
          className={`team-tab ${activeTab === 'basic' ? 'active' : ''}`}
          onClick={() => setActiveTab('basic')}
        >
          基础消息
        </button>
        <button
          className={`team-tab ${activeTab === 'members' ? 'active' : ''}`}
          onClick={() => setActiveTab('members')}
        >
          团队成员
        </button>
      </div>

      {loading ? (
        <div className="team-placeholder">加载中…</div>
      ) : (
        <div className="team-panel">
          {activeTab === 'basic' && (
            <div className="team-form">
              <div className="team-form-field">
                <label>
                  <span className="team-required">*</span>团队名称
                </label>
                <input
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="请输入团队名称"
                />
              </div>
              <div className="team-form-field">
                <label>团队简介</label>
                <div className="team-textarea-wrap">
                  <textarea
                    className="input team-textarea"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    maxLength={20}
                    placeholder="请输入团队简介"
                    rows={3}
                  />
                  <span className="team-char-count">{description.length}/20</span>
                </div>
              </div>
              <div className="team-form-actions">
                <Button
                  variant="outline"
                  className="team-btn-delete"
                  disabled={isLastTeam}
                  onClick={handleDelete}
                >
                  删除团队
                </Button>
                <Button onClick={handleUpdate} disabled={saving}>
                  {saving ? '保存中…' : '确认修改'}
                </Button>
              </div>
              {isLastTeam && (
                <div className="team-warning">
                  当前团队为最后一个团队，无法删除
                </div>
              )}
            </div>
          )}

          {activeTab === 'members' && (
            <div className="team-members-pane">
              <div className="team-members-toolbar">
                <Button icon={<Plus size={16} />} onClick={() => setMemberModalOpen(true)}>
                  添加成员
                </Button>
              </div>
              {members.length === 0 ? (
                <div className="team-empty">暂无成员</div>
              ) : (
                <table className="team-members-table">
                  <thead>
                    <tr>
                      <th>登录账号</th>
                      <th>用户名</th>
                      <th>所属角色</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.id}>
                        <td>{m.account}</td>
                        <td>{m.nickname}</td>
                        <td>{m.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      <AddMemberModal
        open={memberModalOpen}
        existingUserIds={members.map((m) => m.userId)}
        onClose={() => setMemberModalOpen(false)}
        onConfirm={handleAddMembers}
      />
    </div>
  )
}
