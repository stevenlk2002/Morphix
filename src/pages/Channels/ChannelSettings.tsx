/** 特殊渠道设置（SET）：企微接入主体 CRUD，全部走真实后端 /api/channels/wechat-subjects。 */

import { useEffect, useState } from 'react'
import { Plus, HelpCircle } from 'lucide-react'
import Button from '../../components/common/Button'
import Modal from '../../components/common/Modal'
import { channelsApi } from '../../api/client'
import type { WechatSubjectDTO, WechatSubjectInput } from '../../types/channels'
import { toast, errText } from '../../utils/toast'
import '../../pages/prototype.css'
import './ChannelSettings.css'

interface WechatConfigCardProps {
  subject: WechatSubjectDTO
  onSave: (id: string, data: WechatSubjectInput) => void
}

/** 单张企微应用配置卡片。内部维护草稿，保存时校验三字段非空后回写。 */
function WechatConfigCard({ subject, onSave }: WechatConfigCardProps) {
  const [draft, setDraft] = useState<WechatSubjectDTO>(subject)

  const handleSave = () => {
    const fullName = draft.fullName.trim()
    const shortName = draft.shortName.trim()
    const corpId = draft.corpId.trim()
    if (!fullName || !shortName || !corpId) {
      toast('请完整填写企业全称、简称与企业ID')
      return
    }
    onSave(subject.id, { fullName, shortName, corpId })
  }

  return (
    <div className="config-card">
      <div className="config-card-title">企微应用配置</div>
      <div
        className="config-help-line"
        title="企业微信要求管理员扫码授权，以授予本系统代发消息与同步通讯录的权限。"
      >
        为何需要扫码授权？
        <HelpCircle size={14} />
      </div>

      <div className="form-group">
        <label className="form-label">
          企业全称 <span className="required">*</span>
        </label>
        <input
          className="input"
          value={draft.fullName}
          placeholder="请输入企业全称"
          onChange={(e) => setDraft((prev) => ({ ...prev, fullName: e.target.value }))}
        />
      </div>
      <div className="form-group">
        <label className="form-label">
          企业简称 <span className="required">*</span>
        </label>
        <input
          className="input"
          value={draft.shortName}
          placeholder="请输入企业简称"
          onChange={(e) => setDraft((prev) => ({ ...prev, shortName: e.target.value }))}
        />
      </div>
      <div className="form-group">
        <label className="form-label">
          企业ID <span className="required">*</span>
        </label>
        <input
          className="input"
          value={draft.corpId}
          placeholder="请输入企业ID"
          onChange={(e) => setDraft((prev) => ({ ...prev, corpId: e.target.value }))}
        />
      </div>

      <div className="config-card-footer">
        <Button variant="secondary" size="sm" onClick={() => setDraft(subject)}>
          取消
        </Button>
        <Button variant="primary" size="sm" onClick={handleSave}>
          保存
        </Button>
      </div>
    </div>
  )
}

/**
 * 特殊渠道设置页（/channels/settings）。
 * 真实数据：启动即从 /api/channels/wechat-subjects 拉取主体列表，
 * 支持新增（弹窗）与逐卡片保存（PUT /api/channels/wechat-subjects/:id）。
 */
export default function ChannelSettingsPage() {
  const [subjects, setSubjects] = useState<WechatSubjectDTO[]>([])
  const [loading, setLoading] = useState(true)

  const [modalOpen, setModalOpen] = useState(false)
  const [modalFullName, setModalFullName] = useState('')
  const [modalShortName, setModalShortName] = useState('')
  const [modalCorpId, setModalCorpId] = useState('')

  const loadSubjects = () => {
    setLoading(true)
    channelsApi
      .listWechatSubjects()
      .then(setSubjects)
      .catch((e) => toast(`主体加载失败：${errText(e)}`))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadSubjects()
  }, [])

  const openModal = () => {
    setModalFullName('')
    setModalShortName('')
    setModalCorpId('')
    setModalOpen(true)
  }
  const closeModal = () => setModalOpen(false)

  const saveSubject = async () => {
    const fullName = modalFullName.trim()
    const shortName = modalShortName.trim()
    const corpId = modalCorpId.trim()
    if (!fullName || !shortName || !corpId) {
      toast('请完整填写企业全称、简称与企业ID')
      return
    }
    try {
      await channelsApi.createWechatSubject({ fullName, shortName, corpId })
      toast('企微主体已添加')
      closeModal()
      loadSubjects()
    } catch (e) {
      toast(`新增失败：${errText(e)}`)
    }
  }

  const handleCardSave = async (id: string, data: WechatSubjectInput) => {
    try {
      await channelsApi.updateWechatSubject(id, data)
      toast('配置已保存')
      loadSubjects()
    } catch (e) {
      toast(`保存失败：${errText(e)}`)
    }
  }

  return (
    <div className="proto-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">特殊渠道设置</h2>
          <p className="page-subtitle">配置企业微信等特殊渠道的接入主体，用于多渠道协同触达</p>
        </div>
        <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={openModal}>
          新增企微主体
        </Button>
      </div>

      <div className="proto-card">
        <div className="config-section-head">
          <h3 className="config-section-title">特殊渠道配置</h3>
        </div>

        {loading ? (
          <div className="placeholder">
            <p>加载中…</p>
          </div>
        ) : (
          <div className="config-grid">
            {subjects.map((subject) => (
              <WechatConfigCard key={subject.id} subject={subject} onSave={handleCardSave} />
            ))}

            <div
              className="config-card config-card-add"
              role="button"
              tabIndex={0}
              aria-label="新增企微主体"
              onClick={openModal}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  openModal()
                }
              }}
            >
              <div className="config-add-icon">
                <Plus size={20} />
              </div>
              <div className="config-add-text">新增企微主体</div>
            </div>
          </div>
        )}
      </div>

      <Modal
        open={modalOpen}
        title="新增企微主体"
        onClose={closeModal}
        width={480}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={closeModal}>
              取消
            </Button>
            <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={saveSubject}>
              保存
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">
            企业全称 <span className="required">*</span>
          </label>
          <input
            className="input"
            value={modalFullName}
            placeholder="请输入企业全称"
            onChange={(e) => setModalFullName(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            企业简称 <span className="required">*</span>
          </label>
          <input
            className="input"
            value={modalShortName}
            placeholder="请输入企业简称"
            onChange={(e) => setModalShortName(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            企业ID <span className="required">*</span>
          </label>
          <input
            className="input"
            value={modalCorpId}
            placeholder="请输入企业ID"
            onChange={(e) => setModalCorpId(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  )
}
