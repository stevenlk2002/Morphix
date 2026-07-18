import './Placeholder.css'

export default function PlaceholderPage({ title, icon: Icon }) {
  return (
    <div className="placeholder-page">
      <div className="placeholder-content">
        {Icon && <Icon size={48} className="placeholder-icon" />}
        <h2 className="placeholder-title">{title}</h2>
        <p className="placeholder-text">此页面正在开发中...</p>
      </div>
    </div>
  )
}
