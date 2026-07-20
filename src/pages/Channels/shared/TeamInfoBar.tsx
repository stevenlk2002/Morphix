/** ACC 页顶部团队信息条（团队名 / 剩余席位 / 动能值）。 */

interface TeamInfoBarProps {
  /** 团队名。 */
  name: string
  /** 剩余席位。 */
  seatsLeft: number
  /** 动能值。 */
  energyValue: number
}

/**
 * 团队信息条，对齐原型 L7804-7806：
 * 「初始团队 · 剩余席位 1 · 动能值 908」。
 */
export default function TeamInfoBar({ name, seatsLeft, energyValue }: TeamInfoBarProps) {
  return (
    <div className="channel-team-info">
      <span className="channel-team-name">{name}</span>
      <span className="badge badge-default">剩余席位 {seatsLeft}</span>
      <span className="badge badge-default">动能值 {energyValue}</span>
    </div>
  )
}
