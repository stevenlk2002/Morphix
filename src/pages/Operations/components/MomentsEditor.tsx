import { useState, useRef } from 'react'
import { Plus, X, Upload, Sparkles } from 'lucide-react'

export type MomentsChannel = '微信' | '企业微信' | 'WhatsApp'
export type MomentsContentType = '纯文本' | '图文' | '视频' | '链接'

export interface MomentsImage {
  id: string
  name: string
  url: string
}

export interface MomentsLink {
  url: string
  desc: string
  cover?: string
}

export interface MomentsValue {
  channel: MomentsChannel
  contentType: MomentsContentType
  text: string
  images: MomentsImage[]
  video: { name: string; url: string } | null
  link: MomentsLink | null
}

export const DEFAULT_MOMENTS: MomentsValue = {
  channel: '微信',
  contentType: '纯文本',
  text: '',
  images: [],
  video: null,
  link: null,
}

interface Props {
  value: MomentsValue
  onChange: (v: MomentsValue) => void
}

const MAX_IMAGES = 9
const MAX_TEXT = 1000
const MAX_LINK_DESC = 80

function isHttpUrl(s: string) {
  return /^https?:\/\/.+/i.test(s.trim())
}

/** 朋友圈任务参数编辑器：渠道 + 内容类型 + 4 种内容模式。 */
export default function MomentsEditor({ value, onChange }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const setField = <K extends keyof MomentsValue>(k: K, v: MomentsValue[K]) => {
    onChange({ ...value, [k]: v })
  }

  const handleImageFiles = (files: FileList | null) => {
    if (!files) return
    const arr = Array.from(files)
    const remaining = MAX_IMAGES - value.images.length
    const toAdd = arr.slice(0, remaining)
    Promise.all(
      toAdd.map(
        (f) =>
          new Promise<string>((resolve) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result as string)
            reader.readAsDataURL(f)
          })
      )
    ).then((urls) => {
      const imgs: MomentsImage[] = urls.map((url, i) => ({
        id: `img_${Date.now()}_${i}`,
        name: toAdd[i].name,
        url,
      }))
      setField('images', [...value.images, ...imgs])
    })
  }

  const removeImage = (id: string) => {
    setField(
      'images',
      value.images.filter((i) => i.id !== id)
    )
  }

  const handleVideoFile = (files: FileList | null) => {
    if (!files || !files[0]) return
    const f = files[0]
    const url = URL.createObjectURL(f)
    setField('video', { name: f.name, url })
  }

  const handleCoverFile = (files: FileList | null) => {
    if (!files || !files[0]) return
    const f = files[0]
    const reader = new FileReader()
    reader.onload = () => {
      const link = value.link || { url: '', desc: '' }
      setField('link', { ...link, cover: reader.result as string })
    }
    reader.readAsDataURL(f)
  }

  return (
    <div>
      {/* 朋友圈渠道 */}
      <div className="ops-form-group">
        <label className="ops-form-label">
          朋友圈渠道 <span className="required">*</span>
        </label>
        <select
          className="select"
          value={value.channel}
          onChange={(e) => setField('channel', e.target.value as MomentsChannel)}
        >
          <option value="微信">微信</option>
          <option value="企业微信">企业微信</option>
          <option value="WhatsApp">WhatsApp</option>
        </select>
      </div>

      {/* 朋友圈内容类型 */}
      <div className="ops-form-group">
        <label className="ops-form-label">
          朋友圈内容类型 <span className="required">*</span>
        </label>
        <select
          className="select"
          value={value.contentType}
          onChange={(e) => setField('contentType', e.target.value as MomentsContentType)}
        >
          <option value="纯文本">纯文本</option>
          <option value="图文">图文</option>
          <option value="视频">视频</option>
          <option value="链接">链接</option>
        </select>
      </div>

      {/* 朋友圈文字内容 */}
      <div className="ops-form-group">
        <label className="ops-form-label">朋友圈文字内容</label>
        <textarea
          className="input"
          rows={4}
          maxLength={MAX_TEXT}
          placeholder="请输入朋友圈内容"
          value={value.text}
          onChange={(e) => setField('text', e.target.value)}
          style={{ resize: 'vertical' }}
        />
        <div className={`ops-char-count ${value.text.length > MAX_TEXT ? 'over' : ''}`}>
          {value.text.length} / {MAX_TEXT}
        </div>
      </div>

      {/* 纯文本模式 - 只显示文字 */}

      {/* 图文模式 - 文字 + 图片 */}
      {value.contentType === '图文' && (
        <div className="ops-form-group">
          <label className="ops-form-label">
            朋友圈图片内容 <span className="required">*</span>
            <span className="ops-required-tip">（最多 {MAX_IMAGES} 张，鼠标长按可拖拽更换图片顺序）</span>
          </label>
          <div className="ops-moments-image-grid">
            {value.images.map((img) => (
              <div key={img.id} className="ops-moments-image-item">
                <img src={img.url} alt={img.name} />
                <button
                  type="button"
                  className="ops-moments-image-remove"
                  onClick={() => removeImage(img.id)}
                  aria-label="删除图片"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
            {value.images.length < MAX_IMAGES && (
              <button
                type="button"
                className="ops-moments-image-add"
                onClick={() => fileInputRef.current?.click()}
              >
                <Plus size={20} />
                <span>添加图片</span>
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/bmp"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => {
                handleImageFiles(e.target.files)
                e.target.value = ''
              }}
            />
          </div>
        </div>
      )}

      {/* 视频模式 - 文字 + 视频 */}
      {value.contentType === '视频' && (
        <div className="ops-form-group">
          <label className="ops-form-label">
            朋友圈视频内容 <span className="required">*</span>
          </label>
          <label
            className={`ops-dropzone ${dragOver ? 'drag-over' : ''} ${
              value.video ? 'has-file' : ''
            }`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              handleVideoFile(e.dataTransfer.files)
            }}
          >
            {value.video ? (
              <div className="ops-video-preview">
                <video src={value.video.url} controls />
                <div className="ops-video-name">{value.video.name}</div>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setField('video', null)}
                >
                  重新选择
                </button>
              </div>
            ) : (
              <>
                <Upload size={28} className="ops-dropzone-icon" />
                <div>拖拽视频至此，或者<a onClick={(e) => { e.preventDefault(); fileInputRef.current?.click() }}> 上传视频</a></div>
                <div className="ops-dropzone-hint">支持 mp4 格式</div>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4"
              style={{ display: 'none' }}
              onChange={(e) => {
                handleVideoFile(e.target.files)
                e.target.value = ''
              }}
            />
          </label>
        </div>
      )}

      {/* 链接模式 - 文字 + 链接 + 描述 + 封面 */}
      {value.contentType === '链接' && (
        <>
          <div className="ops-form-group">
            <label className="ops-form-label">
              朋友圈链接内容 <span className="required">*</span>
            </label>
            <input
              className={`input ${value.link?.url && !isHttpUrl(value.link.url) ? 'error' : ''}`}
              placeholder="请输入http或https开头的链接"
              value={value.link?.url || ''}
              onChange={(e) => {
                const link = value.link || { url: '', desc: '' }
                setField('link', { ...link, url: e.target.value })
              }}
            />
            {value.link?.url && !isHttpUrl(value.link.url) && (
              <div className="ops-error-text">请输入以http或https开头的有效链接</div>
            )}
          </div>
          <div className="ops-form-group">
            <label className="ops-form-label">卡片描述</label>
            <input
              className="input"
              maxLength={MAX_LINK_DESC}
              placeholder="请输入卡片描述"
              value={value.link?.desc || ''}
              onChange={(e) => {
                const link = value.link || { url: '', desc: '' }
                setField('link', { ...link, desc: e.target.value })
              }}
            />
            <div className={`ops-char-count ${(value.link?.desc?.length || 0) > MAX_LINK_DESC ? 'over' : ''}`}>
              {value.link?.desc?.length || 0} / {MAX_LINK_DESC}
            </div>
          </div>
          <div className="ops-form-group">
            <label className="ops-form-label">卡片封面</label>
            {value.link?.cover ? (
              <div className="ops-moments-image-item" style={{ maxWidth: 160, height: 120 }}>
                <img src={value.link.cover} alt="卡片封面" />
                <button
                  type="button"
                  className="ops-moments-image-remove"
                  onClick={() => {
                    const link = value.link!
                    setField('link', { ...link, cover: undefined })
                  }}
                  aria-label="删除封面"
                >
                  <X size={12} />
                </button>
              </div>
            ) : (
              <label className={`ops-dropzone ${dragOver ? 'drag-over' : ''}`} style={{ minHeight: 120 }}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  handleCoverFile(e.dataTransfer.files)
                }}
              >
                <Upload size={24} className="ops-dropzone-icon" />
                <div>拖拽或点击上传图片</div>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/bmp"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    handleCoverFile(e.target.files)
                    e.target.value = ''
                  }}
                />
              </label>
            )}
          </div>
        </>
      )}

      {value.contentType === '纯文本' && (
        <div className="ops-tip-moments">
          <Sparkles size={14} />
          <span>纯文本模式：仅发送文字内容，不需要上传图片/视频/链接</span>
        </div>
      )}
    </div>
  )
}
