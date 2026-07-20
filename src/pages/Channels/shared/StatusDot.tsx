/** 在线 / 离线 状态点（与原型 `.dot.online` / `.dot.offline` 对齐）。 */

interface StatusDotProps {
  /** 状态：online / offline。 */
  status: 'online' | 'offline' | string
  /** 是否显示文案（如 [ipad在线] / [离线]）。 */
  label?: string
}

/** 状态点（不含文案）。 */
export function StatusDot({ status }: { status: 'online' | 'offline' | string }) {
  const cls = status === 'online' ? 'online' : 'offline'
  return <span className={`dot ${cls}`} />
}

/** 状态点 + 文案组合（如「● 在线」）。 */
export default function StatusLabel({ status, label }: StatusDotProps) {
  const cls = status === 'online' ? 'online' : 'offline'
  return (
    <span className={`session-account-status-dot ${cls}`}>
      <span className="dot" />
      <span>{label ?? (status === 'online' ? '在线' : '离线')}</span>
    </span>
  )
}
