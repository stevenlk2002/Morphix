import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './Button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children?: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  icon?: ReactNode
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  icon,
  className,
  ...props
}: ButtonProps) {
  const classes = ['btn', `btn-${variant}`, `btn-${size}`]
  if (className) classes.push(className)
  return (
    <button className={classes.join(' ')} disabled={disabled} {...props}>
      {icon && <span className="btn-icon">{icon}</span>}
      <span className="btn-label">{children}</span>
    </button>
  )
}
