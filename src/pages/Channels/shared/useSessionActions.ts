import { useCallback } from 'react'
import type { RefObject } from 'react'
import { channelsApi } from '../../../api/client'
import { toast, errText } from '../../../utils/toast'
import type { SessionDTO } from '../../../types/channels'

export interface UseSessionActionsOptions {
  accountId: string
  reloadSessions: () => void
  setSelectedSessionId: (id: string) => void
}

export interface SessionActions {
  scrollToTop: () => void
  scrollToFirstUnread: () => void
  scrollToSelected: () => void
  markAllReadLocal: () => void
}

/**
 * 中栏会话列表的滚动定位与一键已读行为（R5-P0）。
 *
 * - scrollToTop：列表滚动回到顶部。
 * - scrollToFirstUnread：选中第一个 `unreadCount>0` 的会话并滚动定位到它。
 * - scrollToSelected：滚动到当前 `selectedSessionId` 对应的 DOM 项。
 * - markAllReadLocal：调 read-local 接口清本地未读，成功后重载会话列表（后端已持久化）。
 */
export function useSessionActions(
  sessions: SessionDTO[],
  selectedSessionId: string | null,
  listRef: RefObject<HTMLDivElement | null>,
  options: UseSessionActionsOptions
): SessionActions {
  const { accountId, reloadSessions, setSelectedSessionId } = options

  const scrollToItem = useCallback(
    (id: string) => {
      const root = listRef.current
      if (!root) return
      const el = root.querySelector<HTMLElement>(`[data-session-id="${id}"]`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    },
    [listRef]
  )

  const scrollToTop = useCallback(() => {
    const root = listRef.current
    if (root) root.scrollTo({ top: 0, behavior: 'smooth' })
  }, [listRef])

  const scrollToFirstUnread = useCallback(() => {
    const first = sessions.find((s) => s.unreadCount > 0)
    if (!first) {
      toast('当前没有未读会话')
      return
    }
    setSelectedSessionId(first.id)
    // 等选中态渲染完成后再滚动定位
    requestAnimationFrame(() => scrollToItem(first.id))
  }, [sessions, setSelectedSessionId, scrollToItem])

  const scrollToSelected = useCallback(() => {
    if (!selectedSessionId) {
      toast('请先选择一个会话')
      return
    }
    scrollToItem(selectedSessionId)
  }, [selectedSessionId, scrollToItem])

  const markAllReadLocal = useCallback(async () => {
    if (!accountId) return
    try {
      await channelsApi.markSessionsReadLocal(accountId)
      // 本地未读清零并重载会话列表（后端已持久化）
      reloadSessions()
      toast('已将本地未读全部标为已读')
    } catch (e) {
      toast(`一键已读失败：${errText(e)}`)
    }
  }, [accountId, reloadSessions])

  return {
    scrollToTop,
    scrollToFirstUnread,
    scrollToSelected,
    markAllReadLocal,
  }
}
