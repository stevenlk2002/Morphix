import { useEffect, useRef, useState } from 'react'
import { Save } from 'lucide-react'
import Button from '../../components/common/Button'
import { orgApi } from '../../api/client'
import type { OrgInfoDTO } from '../../api/client'
import '../../pages/prototype.css'
import './OrgInfo.css'

/** Banner 右侧 SVG 插画（与原型完全一致）。 */
function BannerIllustration() {
  return (
    <svg width="200" height="120" viewBox="0 0 200 120" aria-hidden="true">
      <rect x="60" y="40" width="80" height="70" rx="6" fill="#fff" opacity="0.5" />
      <rect x="80" y="20" width="40" height="30" rx="4" fill="#fff" opacity="0.4" />
      <rect x="20" y="60" width="30" height="50" rx="4" fill="#fff" opacity="0.3" />
      <rect x="150" y="60" width="30" height="50" rx="4" fill="#fff" opacity="0.3" />
    </svg>
  )
}

export default function OrgInfoPage() {
  const [form, setForm] = useState<OrgInfoDTO>({ orgName: '', contactName: '', contactPhone: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showNotice = (msg: string) => {
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    setNotice(msg)
    noticeTimer.current = setTimeout(() => setNotice(''), 2500)
  }

  useEffect(() => {
    orgApi
      .getInfo()
      .then(setForm)
      .catch(() => showNotice('加载组织信息失败'))
      .finally(() => setLoading(false))
  }, [])

  const update = (patch: Partial<OrgInfoDTO>) => {
    setForm((prev) => ({ ...prev, ...patch }))
  }

  const handleConfirm = async () => {
    setSaving(true)
    try {
      const updated = await orgApi.updateInfo(form)
      setForm(updated)
      showNotice('组织信息已保存')
    } catch {
      showNotice('保存失败，请稍后重试')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="proto-page proto-page-narrow">
        <div className="org-skeleton" />
      </div>
    )
  }

  return (
    <div className="proto-page proto-page-narrow">
      {/* Banner 蓝色渐变 + 右侧 SVG 插画 */}
      <div className="org-banner">
        <div>
          <div className="org-banner-title">组织信息管理</div>
          <div className="org-banner-desc">Organizational Information Management</div>
        </div>
        <BannerIllustration />
      </div>

      <div className="proto-card org-card">
        <div className="org-grid">
          <div className="form-group">
            <label className="form-label">组织名</label>
            <input
              className="input"
              type="text"
              value={form.orgName}
              onChange={(e) => update({ orgName: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">联系人</label>
            <input
              className="input"
              type="text"
              value={form.contactName}
              onChange={(e) => update({ contactName: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">联系方式</label>
            <input
              className="input"
              type="text"
              value={form.contactPhone}
              onChange={(e) => update({ contactPhone: e.target.value })}
            />
          </div>
        </div>

        <div className="org-actions">
          <Button variant="primary" icon={<Save size={14} />} onClick={handleConfirm} disabled={saving}>
            确认
          </Button>
        </div>

        {notice && <div className="proto-notice proto-notice-success org-notice">{notice}</div>}
      </div>
    </div>
  )
}
