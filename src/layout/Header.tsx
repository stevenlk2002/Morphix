import { Search, Bell } from 'lucide-react'
import './Header.css'

interface HeaderProps {
  title: string
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <h1 className="header-title">{title}</h1>
      </div>
      <div className="header-right">
        <button className="header-btn" type="button" aria-label="搜索">
          <Search size={18} />
        </button>
        <button className="header-btn" type="button" aria-label="通知">
          <Bell size={18} />
        </button>
        <div className="header-avatar">Admin</div>
      </div>
    </header>
  )
}
