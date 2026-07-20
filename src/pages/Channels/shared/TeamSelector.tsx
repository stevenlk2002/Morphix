/** SES 顶栏团队选择器（含剩余席位 + 新建/管理占位入口）。 */

import { useState } from 'react'
import { ChevronDown, Plus, Settings } from 'lucide-react'
import type { TeamDTO } from '../../../types/channels'

interface TeamSelectorProps {
  /** 团队列表。 */
  teams: TeamDTO[]
  /** 当前选中团队 id。 */
  currentTeamId: string
  /** 切换团队回调。 */
  onSelect: (teamId: string) => void
}

/**
 * 会话管理顶栏团队选择器，对齐原型 L8088-8102。
 * 下拉含「新建团队」「管理」入口（P2，本期仅占位）。
 */
export default function TeamSelector({ teams, currentTeamId, onSelect }: TeamSelectorProps) {
  const [open, setOpen] = useState(false)
  const current = teams.find((t) => t.id === currentTeamId) ?? teams[0]

  return (
    <div className="team-selector" onClick={(e) => e.stopPropagation()}>
      <div className="team-selector-header">
        <div
          className="team-selector-trigger"
          onClick={(e) => {
            e.stopPropagation()
            setOpen((v) => !v)
          }}
        >
          <span id="currentTeamName">{current?.name ?? '初始团队'}</span>
          <ChevronDown size={14} />
        </div>
      </div>
      {open && (
        <div className="team-selector-dropdown" onClick={(e) => e.stopPropagation()}>
          <button
            className="team-selector-new"
            onClick={(e) => {
              e.stopPropagation()
              setOpen(false)
            }}
          >
            <Plus size={14} /> 新建团队
          </button>
          {teams.map((t) => (
            <div
              key={t.id}
              className={`team-selector-option${t.id === currentTeamId ? ' active' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
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
                }}
              >
                <Settings size={12} /> 管理
              </span>
            </div>
          ))}
        </div>
      )}
      {current && (
        <div className="team-selector-seats">
          <span>剩余席位</span>
          <span className="seats-value">{current.seatsLeft}</span>
        </div>
      )}
    </div>
  )
}
