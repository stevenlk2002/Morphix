import { useState } from 'react'
import { Check, Save } from 'lucide-react'
import Button from '../../components/common/Button'
import type { OrgInfo as OrgInfoType } from '../../types/resource'
import '../../pages/prototype.css'
import './OrgInfo.css'

/** 组织信息种子数据。 */
const DEFAULT_ORG: OrgInfoType = {
  orgName: 'Morphix',
  contactName: '江南竹绿',
  contactPhone: '138****8888',
}

/**
 * 组织信息管理页（/organization/info）。
 * mock-first：使用种子数据 + 本地受控状态，确认后更新本地状态并展示成功提示。
 */
export default function OrgInfoPage() {
  const [form, setForm] = useState<OrgInfoType>(DEFAULT_ORG)
  const [saved, setSaved] = useState(false)

  const update = (patch: Partial<OrgInfoType>) => {
    setForm((prev) => ({ ...prev, ...patch }))
    setSaved(false)
  }

  const handleConfirm = () => {
    // mock：仅更新本地状态并展示成功提示，后续接入后端 API
    setSaved(true)
  }

  return (
    <div className="proto-page proto-page-narrow">
      <div className="page-header">
        <div>
          <h2 className="page-title">组织信息管理</h2>
          <p className="page-subtitle">维护当前租户的组织基本信息，用于合同、发票与工单关联。</p>
        </div>
      </div>

      <div className="proto-card org-card">
        <div className="org-grid">
          <div className="form-group">
            <label className="form-label">
              组织名称 <span className="required">*</span>
            </label>
            <input
              className="input"
              type="text"
              value={form.orgName}
              placeholder="请输入组织名称"
              onChange={(e) => update({ orgName: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              联系人 <span className="required">*</span>
            </label>
            <input
              className="input"
              type="text"
              value={form.contactName}
              placeholder="请输入联系人"
              onChange={(e) => update({ contactName: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              联系方式 <span className="required">*</span>
            </label>
            <input
              className="input"
              type="text"
              value={form.contactPhone}
              placeholder="请输入联系方式"
              onChange={(e) => update({ contactPhone: e.target.value })}
            />
          </div>
        </div>

        <div className="org-actions">
          <Button variant="primary" icon={<Save size={14} />} onClick={handleConfirm}>
            确认
          </Button>
        </div>

        {saved && (
          <div className="proto-notice proto-notice-success">
            <Check size={14} /> 组织信息已保存
          </div>
        )}
      </div>
    </div>
  )
}
