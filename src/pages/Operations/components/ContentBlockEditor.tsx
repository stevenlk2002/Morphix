import { useState, useRef, useCallback } from 'react'
import { Trash2, Plus, Image, Video, FileText, Link, Upload } from 'lucide-react'
import type { ContentBlock, ContentBlockType } from '../../../types/operations'

interface Props {
  blocks: ContentBlock[]
  onChange: (blocks: ContentBlock[]) => void
}

/** 内容块类型 tab 配置。 */
const TYPE_TABS: { key: ContentBlockType; label: string; icon: React.ReactNode }[] = [
  { key: 'text', label: '文本', icon: <FileText size={14} /> },
  { key: 'image', label: '图片', icon: <Image size={14} /> },
  { key: 'video', label: '视频', icon: <Video size={14} /> },
  { key: 'file', label: '文件', icon: <FileText size={14} /> },
  { key: 'card', label: '卡片链接', icon: <Link size={14} /> },
]

/** 格式化文件大小为可读字符串。 */
function formatFileSize(bytes?: number): string {
  if (bytes === undefined || bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** 校验单个 block 是否完整。 */
function validateBlock(block: ContentBlock): boolean {
  switch (block.type) {
    case 'text':
      return block.value.trim().length > 0
    case 'image':
    case 'video':
      return block.value.length > 0
    case 'file':
      return block.value.length > 0
    case 'card': {
      const urlOk = /^https?:\/\/.+/.test(block.url)
      const titleOk = block.title.trim().length > 0
      const descOk = block.desc.trim().length > 0
      return urlOk && titleOk && descOk
    }
    default:
      return false
  }
}

/** 创建空的内容块。 */
function createEmptyBlock(type: ContentBlockType): ContentBlock {
  switch (type) {
    case 'text':
      return { type: 'text', value: '' }
    case 'image':
      return { type: 'image', value: '' }
    case 'video':
      return { type: 'video', value: '' }
    case 'file':
      return { type: 'file', value: '' }
    case 'card':
      return { type: 'card', url: '', title: '', desc: '' }
    case 'moments':
      return { type: 'moments', value: '' }
  }
}

/** 拖拽上传区域组件。 */
function DropZone({
  accept,
  hint,
  onFile,
  children,
}: {
  accept: string
  hint: string
  onFile: (file: File) => void
  children?: React.ReactNode
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dragCounter = useRef(0)

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current++
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current--
    if (dragCounter.current === 0) {
      setDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragging(false)
      dragCounter.current = 0
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onFile(e.dataTransfer.files[0])
      }
    },
    [onFile],
  )

  const handleClick = () => {
    inputRef.current?.click()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFile(e.target.files[0])
      // Reset so the same file can be re-selected
      e.target.value = ''
    }
  }

  if (children) {
    // 已上传：显示预览 + 重新选择按钮
    return (
      <div
        className={`ops-dropzone ${dragging ? 'ops-dropzone-dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        style={{ cursor: 'pointer' }}
      >
        {children}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
      </div>
    )
  }

  return (
    <div
      className={`ops-dropzone ${dragging ? 'ops-dropzone-dragging' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <Upload size={24} style={{ color: 'var(--text-tertiary)', marginBottom: 8 }} />
      <span className="ops-dropzone-hint">{hint}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </div>
  )
}

/** 单个文本内容块。 */
function TextBlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock & { type: 'text' }
  onChange: (b: ContentBlock) => void
}) {
  return (
    <textarea
      className="textarea"
      rows={4}
      placeholder="请填写文本内容"
      value={block.value}
      onChange={(e) => onChange({ ...block, value: e.target.value })}
    />
  )
}

/** 单个图片内容块。 */
function ImageBlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock & { type: 'image' }
  onChange: (b: ContentBlock) => void
}) {
  const handleFile = useCallback(
    (file: File) => {
      const url = URL.createObjectURL(file)
      onChange({ ...block, value: url, name: file.name })
    },
    [block, onChange],
  )

  if (block.value) {
    return (
      <div style={{ position: 'relative' }}>
        <DropZone accept="image/png,image/jpeg,image/bmp" hint="拖拽图片至此，或者上传图片" onFile={handleFile}>
          <img
            src={block.value}
            alt={block.name || '已上传图片'}
            style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 6, display: 'block' }}
          />
        </DropZone>
      </div>
    )
  }

  return <DropZone accept="image/png,image/jpeg,image/bmp" hint="拖拽图片至此，或者上传图片" onFile={handleFile} />
}

/** 单个视频内容块。 */
function VideoBlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock & { type: 'video' }
  onChange: (b: ContentBlock) => void
}) {
  const handleFile = useCallback(
    (file: File) => {
      const url = URL.createObjectURL(file)
      onChange({ ...block, value: url, name: file.name })
    },
    [block, onChange],
  )

  if (block.value) {
    return (
      <DropZone accept="video/mp4" hint="拖拽视频至此，或者上传视频" onFile={handleFile}>
        <video
          src={block.value}
          controls
          style={{ maxWidth: '100%', maxHeight: 260, borderRadius: 6, display: 'block' }}
        />
      </DropZone>
    )
  }

  return <DropZone accept="video/mp4" hint="拖拽视频至此，或者上传视频" onFile={handleFile} />
}

/** 单个文件内容块。 */
function FileBlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock & { type: 'file' }
  onChange: (b: ContentBlock) => void
}) {
  const handleFile = useCallback(
    (file: File) => {
      const url = URL.createObjectURL(file)
      onChange({ ...block, value: url, name: file.name, size: file.size })
    },
    [block, onChange],
  )

  if (block.value) {
    return (
      <DropZone accept="*" hint="拖拽文件至此，或者上传文件" onFile={handleFile}>
        <div className="ops-file-info">
          <FileText size={20} style={{ color: 'var(--primary)', flexShrink: 0 }} />
          <div className="ops-file-details">
            <span className="ops-file-name">{block.name || '未命名文件'}</span>
            {block.size !== undefined && (
              <span className="ops-file-size">{formatFileSize(block.size)}</span>
            )}
          </div>
        </div>
      </DropZone>
    )
  }

  return <DropZone accept="*" hint="拖拽文件至此，或者上传文件" onFile={handleFile} />
}

/** 单个卡片链接内容块。 */
function CardBlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock & { type: 'card' }
  onChange: (b: ContentBlock) => void
}) {
  const handleCoverFile = useCallback(
    (file: File) => {
      const url = URL.createObjectURL(file)
      onChange({ ...block, cover: url })
    },
    [block, onChange],
  )

  return (
    <div className="ops-card-fields">
      <div className="ops-form-group" style={{ marginBottom: 10 }}>
        <label className="ops-card-label">卡片链接</label>
        <input
          className="input"
          placeholder="请输入http或https开头的链接"
          value={block.url}
          onChange={(e) => onChange({ ...block, url: e.target.value })}
        />
        {block.url.length > 0 && !/^https?:\/\/.+/.test(block.url) && (
          <span className="ops-block-error-inline">请输入http或https开头的链接</span>
        )}
      </div>
      <div className="ops-form-group" style={{ marginBottom: 10 }}>
        <label className="ops-card-label">卡片标题</label>
        <input
          className="input"
          maxLength={30}
          placeholder="请输入卡片标题"
          value={block.title}
          onChange={(e) => onChange({ ...block, title: e.target.value })}
        />
        <div className="ops-char-count">{block.title.length} / 30</div>
      </div>
      <div className="ops-form-group" style={{ marginBottom: 10 }}>
        <label className="ops-card-label">卡片描述</label>
        <input
          className="input"
          maxLength={80}
          placeholder="请输入卡片描述"
          value={block.desc}
          onChange={(e) => onChange({ ...block, desc: e.target.value })}
        />
        <div className="ops-char-count">{block.desc.length} / 80</div>
      </div>
      <div className="ops-form-group" style={{ marginBottom: 0 }}>
        <label className="ops-card-label">卡片封面</label>
        {block.cover ? (
          <div style={{ position: 'relative' }}>
            <DropZone accept="image/png,image/jpeg,image/bmp" hint="拖拽图片至此，或者上传图片" onFile={handleCoverFile}>
              <img
                src={block.cover}
                alt="卡片封面"
                style={{ maxWidth: '100%', maxHeight: 160, borderRadius: 6, display: 'block' }}
              />
            </DropZone>
          </div>
        ) : (
          <DropZone accept="image/png,image/jpeg,image/bmp" hint="拖拽图片至此，或者上传图片" onFile={handleCoverFile} />
        )}
      </div>
    </div>
  )
}

/** 渲染单个内容块的编辑器。 */
function BlockEditor({
  block,
  onChange,
}: {
  block: ContentBlock
  onChange: (b: ContentBlock) => void
}) {
  switch (block.type) {
    case 'text':
      return <TextBlockEditor block={block} onChange={onChange} />
    case 'image':
      return <ImageBlockEditor block={block} onChange={onChange} />
    case 'video':
      return <VideoBlockEditor block={block} onChange={onChange} />
    case 'file':
      return <FileBlockEditor block={block} onChange={onChange} />
    case 'card':
      return <CardBlockEditor block={block} onChange={onChange} />
    default:
      return null
  }
}

/** 群发内容块编辑器：支持 5 种内容类型，可添加/删除 block。 */
export default function ContentBlockEditor({ blocks, onChange }: Props) {
  /** 添加新 block（默认 text 类型）。 */
  const handleAddBlock = () => {
    const newBlock = createEmptyBlock('text')
    onChange([...blocks, newBlock])
  }

  /** 删除指定索引的 block。 */
  const handleRemoveBlock = (index: number) => {
    const next = blocks.filter((_, i) => i !== index)
    onChange(next)
  }

  /** 更新指定索引的 block。 */
  const handleUpdateBlock = (index: number, updated: ContentBlock) => {
    const next = [...blocks]
    next[index] = updated
    onChange(next)
  }

  /** 切换 block 类型（切 type 时清空原内容）。 */
  const handleChangeBlockType = (index: number, newType: ContentBlockType) => {
    const current = blocks[index]
    if (current.type === newType) return
    const fresh = createEmptyBlock(newType)
    onChange(blocks.map((b, i) => (i === index ? fresh : b)))
  }

  return (
    <div className="ops-cb-editor">
      {/* Block list —— 每个 block 内部独立选择类型 */}
      <div className="ops-cb-blocks">
        {blocks.map((block, index) => {
          const isValid = validateBlock(block)
          return (
            <div key={index} className="ops-cb-block">
              {/* Header: 5 tab 切换器 + 删除按钮 */}
              <div className="ops-cb-block-header">
                <div className="ops-content-tabs ops-cb-block-tabs">
                  {TYPE_TABS.map((tab) => (
                    <div
                      key={tab.key}
                      className={`ops-content-tab ${block.type === tab.key ? 'active' : ''}`}
                      onClick={() => handleChangeBlockType(index, tab.key)}
                    >
                      {tab.icon}
                      <span style={{ marginLeft: 4 }}>{tab.label}</span>
                    </div>
                  ))}
                </div>
                <button
                  className="ops-cb-block-remove"
                  onClick={() => handleRemoveBlock(index)}
                  aria-label="删除内容块"
                  title="删除"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Content area */}
              <div className="ops-cb-block-body">
                <BlockEditor
                  block={block}
                  onChange={(updated) => handleUpdateBlock(index, updated)}
                />
              </div>

              {/* Validation error */}
              {!isValid && (
                <div className="ops-cb-block-error">请补全群发内容</div>
              )}
            </div>
          )
        })}
      </div>

      {/* Add block button */}
      <button
        type="button"
        className="ops-cb-add-btn"
        onClick={handleAddBlock}
      >
        <Plus size={16} />
        <span>添加群发内容</span>
      </button>
    </div>
  )
}
