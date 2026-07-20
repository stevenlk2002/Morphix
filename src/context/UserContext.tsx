import { createContext, useContext, useState, type ReactNode } from 'react'

/**
 * 应用登录用户模型。
 * 当前为纯前端 mock，字段与高保真原型保持一致。
 */
export interface AppUser {
  name: string
  avatar: string
  tag: string
}

/** 种子用户（与 prototype/index.html 完全一致）。 */
const SEED_USERS: AppUser[] = [
  { name: '江南竹绿', avatar: '江', tag: 'Basic' },
  { name: '管理员-管', avatar: '管', tag: 'Admin' },
  { name: '运营小李', avatar: '李', tag: 'Operator' },
]

/**
 * 模块级开关：当前为纯前端 mock，不连接后端。
 * 接入真实后端时（基于 X-User-Id / X-Role 的 RBAC 鉴权）：
 *   import { setCurrentUser } from '../utils/api'
 *   // 在 switchUser 内调用：await setCurrentUser(u.name)
 * 此处保持 mock，USE_MOCK 为 true 时不会发起任何网络请求。
 */
const USE_MOCK = true

interface UserContextValue {
  currentUser: AppUser
  users: AppUser[]
  switchUser: (user: AppUser) => void
}

const UserContext = createContext<UserContextValue | null>(null)

interface UserProviderProps {
  children: ReactNode
}

export function UserProvider({ children }: UserProviderProps) {
  const [currentUser, setCurrentUser] = useState<AppUser>(SEED_USERS[0])

  const switchUser = (user: AppUser) => {
    if (!USE_MOCK) {
      // 真实后端：await setCurrentUser(user.name)
    }
    setCurrentUser(user)
  }

  return (
    <UserContext.Provider
      value={{ currentUser, users: SEED_USERS, switchUser }}
    >
      {children}
    </UserContext.Provider>
  )
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext)
  if (!ctx) {
    throw new Error('useUser must be used within a UserProvider')
  }
  return ctx
}
