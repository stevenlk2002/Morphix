/**
 * SopCreateCustomer — 客户SOP创建/编辑页。
 *
 * 路由：/operations/sops/create-customer
 * 编辑：/operations/sops/create-customer?id={sopId}
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Save } from 'lucide-react'
import Button from '../../components/common/Button'
import FlowEditor from './components/FlowEditor'
import { sopsApi } from '../../api/sops'
import type { SopNode } from '../../types/sops'
import './SopFlow.css'

export default function SopCreateCustomerPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sopId = searchParams.get('id')

  const [name, setName] = useState('')
  const [nodes, setNodes] = useState<SopNode[]>([])
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)

  const isEdit = !!sopId

  useEffect(() => {
    if (sopId) {
      setLoading(true)
      sopsApi
        .get(sopId)
        .then((data) => {
          setName(data.name)
          setNodes(data.nodes || [])
        })
        .catch((err) => {
          console.error('加载 SOP 失败:', err)
        })
        .finally(() => setLoading(false))
    }
  }, [sopId])

  const handleSave = useCallback(async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setSaving(true)
    try {
      if (isEdit && sopId) {
        await sopsApi.update(sopId, {
          name: trimmed,
          nodes,
        })
      } else {
        await sopsApi.create({
          name: trimmed,
          type: 'customer',
          channel: '企业微信',
          trigger_type: nodes[0]?.config?.triggerType as string || '',
          trigger_config: nodes[0]?.config?.triggerConfig || {},
          nodes,
        })
      }
      navigate('/operations/sops')
    } catch (err) {
      console.error('保存 SOP 失败:', err)
    } finally {
      setSaving(false)
    }
  }, [name, nodes, isEdit, sopId, navigate])

  if (loading) {
    return (
      <div className="proto-page">
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
          加载中...
        </div>
      </div>
    )
  }

  return (
    <div className="proto-page">
      {/* 顶部栏 */}
      <div className="sop-editor-header">
        <div className="sop-editor-name">
          <input
            type="text"
            className="sop-editor-name-input"
            placeholder="输入 SOP 名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={<Save size={14} />}
          onClick={handleSave}
          disabled={!name.trim() || saving}
        >
          {saving ? '保存中...' : '保存'}
        </Button>
      </div>

      {/* 流程编辑器 */}
      <FlowEditor
        initialNodes={nodes}
        isGroup={false}
        onChange={setNodes}
      />
    </div>
  )
}
