/** ACC/SES 顶栏团队选择器（含下拉新建/管理入口）。 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Plus, Settings } from 'lucide-react'
import type { TeamDTO } from '../../../types/channels'

interface TeamSelectorProps {
  /** 团队列表。 */
  teams: TeamDTO[]
  /** 当前选中团队 id。 */
  currentTeamId: string
  /** 切换团队回调（P0 仅 UI 高亮）。 */
  onSelect: (teamId: string) => void
}

/**
 * 团队选择器，对齐原型：
 * 触发器字体与侧边栏登录账号（.brand-name）一致；
 * 下拉含「新建团队」+ 当前团队行「管理」。
 */
export default function TeamSelector({ teams, currentTeamId, onSelect }: TeamSelectorProps) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const current = teams.find((t) => t.id === currentTeamId) ?? teams[0]

  return (
    <div className="team-selector" onClick={(e) => e.stopPropagation()}>
      <div className="team-selector-trigger" onClick={() => setOpen((v) => !v)}>
        <span className="team-selector-name">{current?.name ?? '初始团队'}</span>
        <ChevronDown size={14} />
      </div>

      {current && (
        <div className="team-selector-badges">
          <span className="badge badge-default">剩余席位 {current.seatsLeft}</span>
          <span className="badge badge-default">动能值 {current.energyValue}</span>
        </div>
      )}

      {open && (
        <div className="team-selector-dropdown" onClick={(e) => e.stopPropagation()}>
          <button
            className="team-selector-new"
            onClick={() => {
              setOpen(false)
              navigate('/teams/create')
            }}
          >
            <Plus size={14} /> 新建团队
          </button>
          {teams.map((t) => (
            <div
              key={t.id}
              className={`team-selector-option${t.id === currentTeamId ? ' active' : ''}`}
              onClick={() => {
                onSelect(t.id)
                setOpen(false)
              }}
            >
              <span>{t.name}</span>
              <span
                className="manage"
                onClick={(e) => {
                  e.stopPropagation()
                  setOpen(false)
                  navigate(`/teams/${t.id}/manage`)
                }}
              >
                <Settings size={12} /> 管理
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
