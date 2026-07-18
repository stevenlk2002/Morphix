import { Search, Bell } from 'lucide-react'
import './Header.css'

export default function Header({ title }) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">{title}</h1>
      </div>
      <div className="header-right">
        <button className="header-btn">
          <Search size={18} />
        </button>
        <button className="header-btn">
          <Bell size={18} />
        </button>
        <div className="header-avatar">Admin</div>
      </div>
    </header>
  )
}
