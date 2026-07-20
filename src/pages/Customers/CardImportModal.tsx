import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import Modal from '../../components/common/Modal'
import Button from '../../components/common/Button'
import { toast } from '../../utils/toast'

interface Props {
  open: boolean
  onClose: () => void
}

/**
 * 名片导入弹窗（原型 6890-6907）。
 * P0：仅 UI 占位 + mock 提交（toast 提示）。
 */
export default function CardImportModal({ open, onClose }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [previewFiles, setPreviewFiles] = useState<File[]>([])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setPreviewFiles((prev) => [...prev, ...files])
  }

  const handleImport = () => {
    toast('名片导入任务已提交')
    setPreviewFiles([])
    onClose()
  }

  return (
    <Modal
      open={open}
      title="名片导入"
      onClose={() => {
        setPreviewFiles([])
        onClose()
      }}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={() => { setPreviewFiles([]); onClose() }}>
            取消
          </Button>
          <Button variant="primary" size="sm" onClick={handleImport}>
            开始导入
          </Button>
        </>
      }
    >
      <div className="card-import-body">
        <div
          className="card-import-dropzone"
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="card-import-icon">
            <Upload size={40} />
          </div>
          <div className="card-import-title">
            拖拽名片图片到此处，或
            <span style={{ color: 'var(--primary)', fontWeight: 600 }}>点击选择文件</span>
          </div>
          <div className="card-import-hint">支持 JPG / PNG / PDF 格式，可批量上传名片</div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </div>
        {previewFiles.length > 0 && (
          <div className="card-import-preview">
            {previewFiles.map((f, i) => (
              <span key={i} className="tag-chip">
                {f.name}
              </span>
            ))}
          </div>
        )}
        <div className="card-import-tip">
          名片导入后，系统将自动识别姓名、电话、公司等信息并创建为客户。导入前请确认已选择正确的私域账号与触达渠道。
        </div>
      </div>
    </Modal>
  )
}
