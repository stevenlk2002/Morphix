/** 新建团队向导：Step1 基础信息 → Step2 添加成员。 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus } from 'lucide-react'
import Button from '../../components/common/Button'
import { channelsApi } from '../../api/client'
import AddMemberModal from './shared/AddMemberModal'
import { toast, errText } from '../../utils/toast'
import './Teams.css'

export default function TeamCreatePage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<1 | 2>(1)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [memberModalOpen, setMemberModalOpen] = useState(false)
  const [createdTeamId, setCreatedTeamId] = useState<string | null>(null)

  const handleNext = () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast('请输入团队名称')
      return
    }
    setStep(2)
  }

  const createTeamCore = async () => {
    const trimmed = name.trim()
    setCreating(true)
    try {
      const team = await channelsApi.createTeam({
        name: trimmed,
        description: description.trim(),
      })
      setCreatedTeamId(team.id)
      return team.id
    } catch (e) {
      toast(`创建失败：${errText(e)}`)
      return null
    } finally {
      setCreating(false)
    }
  }

  const handleAddMembers = async (userIds: string[]) => {
    let teamId = createdTeamId
    if (!teamId) {
      teamId = await createTeamCore()
    }
    if (!teamId) return

    try {
      const res = await channelsApi.addTeamMembers(teamId, userIds)
      toast(`已创建团队并添加 ${res.added} 位成员`)
      navigate(`/teams/${teamId}/manage`)
    } catch (e) {
      toast(`添加成员失败：${errText(e)}`)
    }
  }

  const handleSkip = async () => {
    const teamId = await createTeamCore()
    if (teamId) {
      toast('团队创建成功')
      navigate(`/teams/${teamId}/manage`)
    }
  }

  const handleOpenMemberModal = async () => {
    const teamId = await createTeamCore()
    if (teamId) {
      setMemberModalOpen(true)
    }
  }

  return (
    <div className="team-page team-create">
      <div className="team-page-header">
        <button className="team-back" onClick={() => navigate(-1)}>
          <ArrowLeft size={18} />
          <span>返回</span>
        </button>
      </div>

      <div className="team-create-card">
        <div className="team-create-title">新建团队</div>

        <div className="stepper">
          <div className={`step ${step >= 1 ? 'active' : ''}`}>
            <span className="step-num">1</span>
            <span>设置团队基础信息</span>
          </div>
          <div className="step-line" />
          <div className={`step ${step >= 2 ? 'active' : ''}`}>
            <span className="step-num">2</span>
            <span>添加团队成员</span>
          </div>
        </div>

        {step === 1 && (
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
            <Button className="team-create-next" onClick={handleNext} disabled={creating}>
              下一步
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="team-create-step2">
            <div className="team-create-hint">团队基础信息已保存，可立即添加成员或稍后再说。</div>
            <div className="team-create-step2-actions">
              <Button variant="outline" onClick={handleSkip} disabled={creating}>
                稍后再说
              </Button>
              <Button
                icon={<Plus size={16} />}
                onClick={handleOpenMemberModal}
                disabled={creating}
              >
                添加成员
              </Button>
            </div>
          </div>
        )}
      </div>

      <AddMemberModal
        open={memberModalOpen}
        existingUserIds={[]}
        onClose={() => setMemberModalOpen(false)}
        onConfirm={handleAddMembers}
      />
    </div>
  )
}
