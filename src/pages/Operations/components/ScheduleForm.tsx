import { useState, useCallback } from 'react'
import { X, Sparkles } from 'lucide-react'
import type { ScheduleConfig, ScheduleType } from '../../../types/operations'
import { RUN_FREQUENCY_OPTIONS } from '../../../types/operations'
import { operationsTasksApi } from '../../../api/operations'
import Modal from '../../../components/common/Modal'

// ---- 常量 ----

const SCHEDULE_TYPE_MAP: Record<string, ScheduleType> = {
  '一次': 'once',
  '每天': 'daily',
  '每周': 'weekly',
  '每月': 'monthly',
  'Cron表达式': 'cron',
}

const HOURS: string[] = Array.from({ length: 24 }, (_, i) =>
  String(i).padStart(2, '0') + ':00',
)

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const MONTH_DAYS = Array.from({ length: 31 }, (_, i) => i + 1)

// ---- Props ----

interface Props {
  value: ScheduleConfig
  onChange: (config: ScheduleConfig) => void
}

// ---- Helpers ----

function toggleInArray<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]
}

// ---- Sub-components ----

/** 时间 Chip 网格（6列 × 4行，00:00–23:00）。 */
function TimeChipGrid({
  selected,
  onToggle,
}: {
  selected: string[]
  onToggle: (time: string) => void
}) {
  return (
    <div className="ops-time-grid">
      {HOURS.map((h) => (
        <button
          key={h}
          type="button"
          className={`ops-time-chip ${selected.includes(h) ? 'active' : ''}`}
          onClick={() => onToggle(h)}
          aria-pressed={selected.includes(h)}
        >
          {h}
        </button>
      ))}
    </div>
  )
}

/** 可删除 Chip 列表。 */
function ChipList({
  items,
  onRemove,
  emptyText,
}: {
  items: string[]
  onRemove: (item: string) => void
  emptyText?: string
}) {
  if (items.length === 0) {
    return emptyText ? (
      <div className="ops-chip-empty">{emptyText}</div>
    ) : null
  }
  return (
    <div className="ops-chip-list">
      {items.map((item) => (
        <span key={item} className="ops-chip">
          <span>{item}</span>
          <button
            type="button"
            className="ops-chip-remove"
            onClick={() => onRemove(item)}
            aria-label={`移除 ${item}`}
          >
            <X size={12} />
          </button>
        </span>
      ))}
    </div>
  )
}

/** 日期范围选择器。 */
function DateRangeInput({
  start,
  end,
  onStartChange,
  onEndChange,
}: {
  start: string
  end: string
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
}) {
  return (
    <div className="ops-date-range">
      <input
        className="input"
        type="date"
        value={start}
        onChange={(e) => onStartChange(e.target.value)}
        aria-label="生效开始日期"
      />
      <span>—</span>
      <input
        className="input"
        type="date"
        value={end}
        onChange={(e) => onEndChange(e.target.value)}
        aria-label="生效结束日期"
      />
    </div>
  )
}

/** Weekday chip selector (Mon–Sun, multi-select). */
function WeekdayChips({
  selected,
  onToggle,
}: {
  selected: number[]
  onToggle: (d: number) => void
}) {
  return (
    <div className="ops-chip-row">
      {WEEKDAYS.map((label, idx) => {
        const day = idx + 1
        return (
          <button
            key={label}
            type="button"
            className={`ops-chip-select ${selected.includes(day) ? 'active' : ''}`}
            onClick={() => onToggle(day)}
            aria-pressed={selected.includes(day)}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

/** Day-of-month chip selector (1–31). */
function MonthDayChips({
  selected,
  onToggle,
  onSelectAll,
}: {
  selected: number[]
  onToggle: (d: number) => void
  onSelectAll: () => void
}) {
  const allSelected = selected.length === 31
  return (
    <div className="ops-chip-row ops-chip-row-wrap">
      <button
        type="button"
        className={`ops-chip-select ops-chip-select-all ${allSelected ? 'active' : ''}`}
        onClick={onSelectAll}
      >
        全选
      </button>
      {MONTH_DAYS.map((d) => (
        <button
          key={d}
          type="button"
          className={`ops-chip-select ${selected.includes(d) ? 'active' : ''}`}
          onClick={() => onToggle(d)}
          aria-pressed={selected.includes(d)}
        >
          {d}日
        </button>
      ))}
    </div>
  )
}

/** Last-N-days chip selector (第1天–第5天). */
function LastDayChips({
  selected,
  onToggle,
}: {
  selected: number[]
  onToggle: (d: number) => void
}) {
  return (
    <div className="ops-chip-row">
      {[1, 2, 3, 4, 5].map((d) => (
        <button
          key={d}
          type="button"
          className={`ops-chip-select ${selected.includes(d) ? 'active' : ''}`}
          onClick={() => onToggle(d)}
          aria-pressed={selected.includes(d)}
        >
          第{d}天
        </button>
      ))}
    </div>
  )
}

/** AI Cron Modal. */
function AICronModal({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean
  onClose: () => void
  onConfirm: (cron: string) => void
}) {
  const [prompt, setPrompt] = useState('')
  const [generatedCron, setGeneratedCron] = useState('')
  const [explanation, setExplanation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      setError('请输入描述内容')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await operationsTasksApi.aiCron(prompt.trim())
      setGeneratedCron(res.cron || '')
      setExplanation(res.explanation || '')
    } catch {
      setError('AI 生成失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [prompt])

  const handleConfirm = useCallback(() => {
    if (generatedCron) {
      onConfirm(generatedCron)
      // reset
      setPrompt('')
      setGeneratedCron('')
      setExplanation('')
      setError('')
    }
  }, [generatedCron, onConfirm])

  return (
    <Modal
      open={open}
      title="AI 生成 Cron 表达式"
      onClose={() => {
        setPrompt('')
        setGeneratedCron('')
        setExplanation('')
        setError('')
        onClose()
      }}
      width={520}
      footer={
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', width: '100%' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setPrompt('')
              setGeneratedCron('')
              setExplanation('')
              setError('')
              onClose()
            }}
          >
            取消
          </button>
          {generatedCron && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleConfirm}
            >
              确定
            </button>
          )}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="ops-form-group">
          <label className="ops-form-label">描述你的调度需求</label>
          <textarea
            className="textarea"
            rows={3}
            placeholder="例如：每周一到周五早上9点执行"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleGenerate}
          disabled={loading || !prompt.trim()}
          style={{ alignSelf: 'flex-start' }}
        >
          {loading ? '生成中...' : '生成'}
        </button>
        {error && <div className="ops-error-text">{error}</div>}
        {generatedCron && (
          <div className="ops-ai-result">
            <div className="ops-ai-result-label">生成的 Cron 表达式</div>
            <code className="ops-ai-cron-code">{generatedCron}</code>
            {explanation && (
              <div className="ops-ai-explanation">{explanation}</div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

// ---- 主组件 ----

export default function ScheduleForm({ value, onChange }: Props) {
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [monthlyTab, setMonthlyTab] = useState<'days' | 'lastDays'>('days')
  const [customTimeInput, setCustomTimeInput] = useState('')

  const currentType = value.type
  const freqLabel = RUN_FREQUENCY_OPTIONS.find(
    (o) => SCHEDULE_TYPE_MAP[o.value] === currentType,
  )?.value || '一次'

  const handleTypeChange = useCallback(
    (freqLabel: string) => {
      const st = SCHEDULE_TYPE_MAP[freqLabel] || 'once'
      if (st === currentType) return
      switch (st) {
        case 'once':
          onChange({ type: 'once', runTime: '' })
          break
        case 'daily':
          onChange({ type: 'daily', runTimes: [], effectiveStart: '', effectiveEnd: '' })
          break
        case 'weekly':
          onChange({ type: 'weekly', weekdays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
          break
        case 'monthly':
          onChange({ type: 'monthly', days: [], lastDays: [], runTimes: [], effectiveStart: '', effectiveEnd: '' })
          break
        case 'cron':
          onChange({ type: 'cron', cron: '' })
          break
      }
    },
    [currentType, onChange],
  )

  return (
    <div>
      {/* ---- 运行频率 Radio ---- */}
      <div className="ops-form-group">
        <label className="ops-form-label">
          运行频率 <span className="required">*</span>
        </label>
        <div className="ops-freq-radio-group">
          {RUN_FREQUENCY_OPTIONS.map((opt) => (
            <label key={opt.value}>
              <input
                type="radio"
                name="ops-freq"
                checked={freqLabel === opt.value}
                onChange={() => handleTypeChange(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      {/* ---- 模式 1：单次运行 ---- */}
      {currentType === 'once' && (
        <div className="ops-form-group">
          <label className="ops-form-label">
            运行时间 <span className="required">*</span>
          </label>
          <input
            className="input"
            type="datetime-local"
            value={value.runTime}
            onChange={(e) => onChange({ ...value, runTime: e.target.value })}
          />
        </div>
      )}

      {/* ---- 模式 2：每天 ---- */}
      {currentType === 'daily' && (
        <>
          <div className="ops-form-group">
            <label className="ops-form-label">运行时间</label>
            <ChipList
              items={value.runTimes}
              onRemove={(t) =>
                onChange({ ...value, runTimes: value.runTimes.filter((x) => x !== t) })
              }
              emptyText="暂未选择时间"
            />
            <TimeChipGrid
              selected={value.runTimes}
              onToggle={(t) =>
                onChange({ ...value, runTimes: toggleInArray(value.runTimes, t) })
              }
            />
            <div className="ops-add-time-row">
              <input
                className="input ops-time-input-sm"
                type="time"
                value={customTimeInput}
                onChange={(e) => setCustomTimeInput(e.target.value)}
                placeholder="自定义时间"
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  if (customTimeInput && !value.runTimes.includes(customTimeInput)) {
                    onChange({ ...value, runTimes: [...value.runTimes, customTimeInput].sort() })
                    setCustomTimeInput('')
                  }
                }}
                disabled={!customTimeInput}
              >
                + 添加时间
              </button>
            </div>
          </div>

          <div className="ops-form-group">
            <label className="ops-form-label">生效时间</label>
            <DateRangeInput
              start={value.effectiveStart}
              end={value.effectiveEnd}
              onStartChange={(v) => onChange({ ...value, effectiveStart: v })}
              onEndChange={(v) => onChange({ ...value, effectiveEnd: v })}
            />
          </div>
        </>
      )}

      {/* ---- 模式 3：每周 ---- */}
      {currentType === 'weekly' && (
        <>
          <div className="ops-form-group">
            <label className="ops-form-label">选择星期</label>
            <WeekdayChips
              selected={value.weekdays}
              onToggle={(d) =>
                onChange({ ...value, weekdays: toggleInArray(value.weekdays, d).sort() })
              }
            />
          </div>

          <div className="ops-form-group">
            <label className="ops-form-label">运行时间</label>
            <ChipList
              items={value.runTimes}
              onRemove={(t) =>
                onChange({ ...value, runTimes: value.runTimes.filter((x) => x !== t) })
              }
              emptyText="暂未选择时间"
            />
            <TimeChipGrid
              selected={value.runTimes}
              onToggle={(t) =>
                onChange({ ...value, runTimes: toggleInArray(value.runTimes, t) })
              }
            />
            <div className="ops-add-time-row">
              <input
                className="input ops-time-input-sm"
                type="time"
                value={customTimeInput}
                onChange={(e) => setCustomTimeInput(e.target.value)}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  if (customTimeInput && !value.runTimes.includes(customTimeInput)) {
                    onChange({ ...value, runTimes: [...value.runTimes, customTimeInput].sort() })
                    setCustomTimeInput('')
                  }
                }}
                disabled={!customTimeInput}
              >
                + 添加时间
              </button>
            </div>
          </div>

          <div className="ops-form-group">
            <label className="ops-form-label">生效时间</label>
            <DateRangeInput
              start={value.effectiveStart}
              end={value.effectiveEnd}
              onStartChange={(v) => onChange({ ...value, effectiveStart: v })}
              onEndChange={(v) => onChange({ ...value, effectiveEnd: v })}
            />
          </div>
        </>
      )}

      {/* ---- 模式 4：每月 ---- */}
      {currentType === 'monthly' && (
        <>
          <div className="ops-form-group">
            <label className="ops-form-label">指定方式</label>
            <div className="ops-monthly-tabs">
              <button
                type="button"
                className={`ops-monthly-tab ${monthlyTab === 'days' ? 'active' : ''}`}
                onClick={() => setMonthlyTab('days')}
              >
                指定日期
              </button>
              <button
                type="button"
                className={`ops-monthly-tab ${monthlyTab === 'lastDays' ? 'active' : ''}`}
                onClick={() => setMonthlyTab('lastDays')}
              >
                当月倒数第几天
              </button>
            </div>
          </div>

          {monthlyTab === 'days' && (
            <div className="ops-form-group">
              <MonthDayChips
                selected={value.days}
                onToggle={(d) =>
                  onChange({ ...value, days: toggleInArray(value.days, d).sort((a, b) => a - b) })
                }
                onSelectAll={() =>
                  onChange({
                    ...value,
                    days: value.days.length === 31 ? [] : MONTH_DAYS.slice(),
                  })
                }
              />
            </div>
          )}

          {monthlyTab === 'lastDays' && (
            <div className="ops-form-group">
              <LastDayChips
                selected={value.lastDays}
                onToggle={(d) =>
                  onChange({ ...value, lastDays: toggleInArray(value.lastDays, d).sort() })
                }
              />
            </div>
          )}

          <div className="ops-form-group">
            <label className="ops-form-label">运行时间</label>
            <ChipList
              items={value.runTimes}
              onRemove={(t) =>
                onChange({ ...value, runTimes: value.runTimes.filter((x) => x !== t) })
              }
              emptyText="暂未选择时间"
            />
            <TimeChipGrid
              selected={value.runTimes}
              onToggle={(t) =>
                onChange({ ...value, runTimes: toggleInArray(value.runTimes, t) })
              }
            />
            <div className="ops-add-time-row">
              <input
                className="input ops-time-input-sm"
                type="time"
                value={customTimeInput}
                onChange={(e) => setCustomTimeInput(e.target.value)}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  if (customTimeInput && !value.runTimes.includes(customTimeInput)) {
                    onChange({ ...value, runTimes: [...value.runTimes, customTimeInput].sort() })
                    setCustomTimeInput('')
                  }
                }}
                disabled={!customTimeInput}
              >
                + 添加时间
              </button>
            </div>
          </div>

          <div className="ops-form-group">
            <label className="ops-form-label">生效时间</label>
            <DateRangeInput
              start={value.effectiveStart}
              end={value.effectiveEnd}
              onStartChange={(v) => onChange({ ...value, effectiveStart: v })}
              onEndChange={(v) => onChange({ ...value, effectiveEnd: v })}
            />
          </div>
        </>
      )}

      {/* ---- 模式 5：Cron 表达式 ---- */}
      {currentType === 'cron' && (
        <div className="ops-form-group">
          <label className="ops-form-label">Cron 表达式</label>
          <div className="ops-cron-input-row">
            <input
              className="input"
              placeholder="请输入 Cron 表达式，如：0 8 * * 1-5"
              value={value.cron}
              onChange={(e) => onChange({ ...value, cron: e.target.value })}
            />
            <button
              type="button"
              className="btn btn-warning btn-sm ops-ai-cron-btn"
              onClick={() => setAiModalOpen(true)}
            >
              <Sparkles size={14} />
              AI 生成表达式
            </button>
          </div>
          {value.cron === '' && (
            <div className="ops-error-text">请输入 Cron 表达式</div>
          )}
          <div className="ops-cron-hint">示例：每10分钟触发1次；每周二下午三点触发；每年4月最后一个周日8点触发</div>
        </div>
      )}

      {/* AI Cron Modal */}
      <AICronModal
        open={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onConfirm={(cron) => {
          if (value.type === 'cron') {
            onChange({ ...value, cron })
          }
          setAiModalOpen(false)
        }}
      />
    </div>
  )
}
