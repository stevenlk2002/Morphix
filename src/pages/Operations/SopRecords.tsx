/**
 * SOP 运行记录页面（/operations/sops/:id/records）。
 *
 * 功能：
 * - 顶部：← 返回按钮 + SOP 名称
 * - Tab 栏：运行记录（active）+ 后续扩展占位
 * - 表格 4 列：运行时间 / 运行状态 / 异常原因 / 操作
 * - 空态：SVG 插画 + "暂无运行记录"
 * - 加载态、错误处理
 */
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { sopsApi } from '../../api/sops'
import type { SopItem, SopRecord } from '../../types/sops'
import { RECORD_STATUS_LABELS } from '../../types/sops'
import '../../pages/prototype.css'
import './SopRecords.css'

/** 空态 SVG 插画 */
const EMPTY_SVG = (
  <svg width="96" height="96" viewBox="0 0 96 96" fill="none" className="sop-records-empty-illustration" aria-hidden="true">
    <rect x="16" y="20" width="64" height="48" rx="6" fill="#eef2ff" stroke="#c7d2fe" strokeWidth="2" />
    <rect x="24" y="28" width="48" height="6" rx="3" fill="#e0e7ff" />
    <rect x="24" y="38" width="40" height="5" rx="2.5" fill="#e0e7ff" />
    <rect x="24" y="47" width="44" height="5" rx="2.5" fill="#e0e7ff" />
    <rect x="24" y="56" width="36" height="5" rx="2.5" fill="#e0e7ff" />
    <circle cx="68" cy="40" r="14" fill="#f5f3ff" stroke="#c7d2fe" strokeWidth="1.5" />
    <path d="M63 39l3 3 6-5" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

/** 运行状态标签颜色 */
function statusClass(status: string): string {
  if (status === 'success') return 'proto-badge-success'
  if (status === 'failed') return 'proto-badge-danger'
  return 'proto-badge-neutral'
}

export default function SopRecordsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [sop, setSop] = useState<SopItem | null>(null)
  const [records, setRecords] = useState<SopRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [sopData, recordsData] = await Promise.all([
        sopsApi.get(id),
        sopsApi.listRecords(id),
      ])
      setSop(sopData)
      setRecords(recordsData)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '加载失败'
      setError(message)
      console.error('加载运行记录失败:', err)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadData()
  }, [loadData])

  const goBack = () => navigate('/operations/sops')

  return (
    <div className="proto-page">
      {/* 顶部导航 */}
      <div className="sop-records-header">
        <button type="button" className="sop-records-back" onClick={goBack}>
          <ArrowLeft size={18} />
          <span>返回</span>
        </button>
        <h2 className="sop-records-title">
          {sop ? sop.name : '加载中...'}
        </h2>
      </div>

      {/* Tab 栏 */}
      <div className="sop-records-tabs">
        <button type="button" className="sop-records-tab active">
          运行记录
        </button>
        {/* 后续 P0 不实现的 tab 占位 */}
      </div>

      {/* 内容区 */}
      {error ? (
        <div className="sop-records-error">
          <p>{error}</p>
          <button type="button" className="proto-btn proto-btn-sm" onClick={loadData}>
            重试
          </button>
        </div>
      ) : loading ? (
        <div className="sop-records-empty">
          <p className="sop-records-empty-text">加载中...</p>
        </div>
      ) : records.length === 0 ? (
        /* 空态 */
        <div className="sop-records-empty">
          {EMPTY_SVG}
          <p className="sop-records-empty-text">暂无运行记录</p>
        </div>
      ) : (
        /* 记录表格 */
        <div className="sop-records-table-wrap">
          <table className="sop-records-table">
            <thead>
              <tr>
                <th>运行时间</th>
                <th>运行状态</th>
                <th>异常原因</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => (
                <tr key={rec.id}>
                  <td className="sop-records-time">{rec.run_time}</td>
                  <td>
                    <span className={`proto-badge ${statusClass(rec.run_status)}`}>
                      {RECORD_STATUS_LABELS[rec.run_status] || rec.run_status}
                    </span>
                  </td>
                  <td className="sop-records-error-msg">
                    {rec.error_message || '-'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="proto-btn proto-btn-ghost proto-btn-sm"
                      onClick={() => alert(`记录 ID: ${rec.id}\n状态: ${rec.run_status}`)}
                    >
                      详情
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
