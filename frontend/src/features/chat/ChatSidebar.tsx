import { useState, type KeyboardEvent, type MouseEvent } from 'react'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { logout } from '../auth/authSlice'
import ConfirmModal from './ConfirmModal'
import { createChat, deleteChat, renameChat, selectChat, type ChatSummary } from './chatSlice'

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.75}
      stroke="currentColor"
      className="h-4 w-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
      />
    </svg>
  )
}

function LogoutIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.75}
      stroke="currentColor"
      className="h-4 w-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3-3H9m11.25 0l-3-3m3 3l-3 3"
      />
    </svg>
  )
}

function initials(name: string, email: string) {
  const trimmed = name.trim()
  if (trimmed) {
    const parts = trimmed.split(/\s+/)
    return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
  }
  return email[0]?.toUpperCase() ?? '?'
}

function PencilIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.75}
      stroke="currentColor"
      className="h-4 w-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125"
      />
    </svg>
  )
}

interface ChatGroup {
  label: string
  chats: ChatSummary[]
}

const DAY_MS = 24 * 60 * 60 * 1000

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

// One rule for every bucket — how many calendar days ago a chat was created —
// rather than separate special-cased logic per label.
function groupChatsByDate(chats: ChatSummary[]): ChatGroup[] {
  const today = startOfDay(new Date())
  const buckets: Record<string, ChatSummary[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 Days': [],
    Older: [],
  }

  for (const chat of chats) {
    const daysAgo = Math.round(
      (today.getTime() - startOfDay(new Date(chat.created_at)).getTime()) / DAY_MS,
    )
    if (daysAgo <= 0) buckets.Today.push(chat)
    else if (daysAgo === 1) buckets.Yesterday.push(chat)
    else if (daysAgo <= 7) buckets['Previous 7 Days'].push(chat)
    else buckets.Older.push(chat)
  }

  return Object.entries(buckets)
    .filter(([, chatsInBucket]) => chatsInBucket.length > 0)
    .map(([label, chatsInBucket]) => ({ label, chats: chatsInBucket }))
}

function ChatSidebar() {
  const dispatch = useAppDispatch()
  const { chats, activeChatId } = useAppSelector((state) => state.chat)
  const currentUser = useAppSelector((state) => state.auth.user)
  const [pendingDelete, setPendingDelete] = useState<ChatSummary | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const visibleChats = chats.filter((chat) =>
    chat.title.toLowerCase().includes(searchQuery.trim().toLowerCase()),
  )
  const groups = groupChatsByDate(visibleChats)

  function handleDeleteClick(e: MouseEvent, chat: ChatSummary) {
    e.stopPropagation()
    setPendingDelete(chat)
  }

  function confirmDelete() {
    if (pendingDelete) dispatch(deleteChat(pendingDelete.id))
    setPendingDelete(null)
  }

  function startEditing(e: MouseEvent, chat: ChatSummary) {
    e.stopPropagation()
    setEditingId(chat.id)
    setEditValue(chat.title)
  }

  function commitEdit(chat: ChatSummary) {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== chat.title) {
      dispatch(renameChat({ chatId: chat.id, title: trimmed }))
    }
    setEditingId(null)
  }

  function handleEditKeyDown(e: KeyboardEvent<HTMLInputElement>, chat: ChatSummary) {
    if (e.key === 'Enter') {
      e.preventDefault()
      commitEdit(chat)
    } else if (e.key === 'Escape') {
      setEditingId(null)
    }
  }

  function renderChatRow(chat: ChatSummary) {
    if (editingId === chat.id) {
      return (
        <input
          key={chat.id}
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => handleEditKeyDown(e, chat)}
          onBlur={() => commitEdit(chat)}
          onClick={(e) => e.stopPropagation()}
          autoFocus
          className="mb-1 block w-full truncate rounded-md border border-primary bg-beige-soft px-3 py-2 text-left text-[13px] text-ink outline-none"
        />
      )
    }
    return (
      <div key={chat.id} className="group relative mb-1">
        <button
          type="button"
          onClick={() => dispatch(selectChat(chat.id))}
          className={`block w-full truncate rounded-md py-2 pl-3 pr-14 text-left text-[13px] ${
            chat.id === activeChatId
              ? 'bg-primary-light font-semibold text-ink'
              : 'text-ink hover:bg-beige-soft'
          }`}
        >
          {chat.title}
        </button>
        <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-1">
          <button
            type="button"
            onClick={(e) => startEditing(e, chat)}
            aria-label="Rename chat"
            className="cursor-pointer text-muted opacity-0 hover:text-ink group-hover:opacity-100"
          >
            <PencilIcon />
          </button>
          <button
            type="button"
            onClick={(e) => handleDeleteClick(e, chat)}
            aria-label="Delete chat"
            className="cursor-pointer text-red-600 opacity-0 hover:text-red-700 group-hover:opacity-100"
          >
            <TrashIcon />
          </button>
        </div>
      </div>
    )
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-line bg-beige">
      <div className="p-3">
        <h1 className="mb-3 px-1 text-[17px] font-bold tracking-tight text-ink">Threadline</h1>
        <button
          type="button"
          onClick={() => dispatch(createChat())}
          className="w-full rounded-md border border-line bg-beige-soft px-3 py-2 text-[13px] font-semibold text-ink hover:bg-primary-light"
        >
          + New chat
        </button>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search chats..."
          className="mt-2 w-full rounded-md border border-line bg-beige-soft px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-primary"
        />
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {visibleChats.length === 0 && (
          <p className="px-3 py-2 text-[13px] text-muted">No chats found.</p>
        )}
        {groups.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
              {group.label}
            </p>
            {group.chats.map((chat) => renderChatRow(chat))}
          </div>
        ))}
      </nav>
      {currentUser && (
        <div className="flex items-center gap-2.5 border-t border-line px-3 py-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-light text-[12px] font-semibold text-primary">
            {initials(currentUser.name, currentUser.email)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-ink">
              {currentUser.name || currentUser.email}
            </p>
            <p className="truncate text-[11.5px] text-muted">{currentUser.email}</p>
          </div>
          <button
            type="button"
            onClick={() => dispatch(logout())}
            aria-label="Log out"
            className="shrink-0 text-muted hover:text-ink"
          >
            <LogoutIcon />
          </button>
        </div>
      )}
      <ConfirmModal
        open={pendingDelete !== null}
        title="Delete this chat?"
        description={`This will permanently delete "${pendingDelete?.title ?? ''}" and everything discussed in it. This cannot be undone.`}
        confirmLabel="Delete"
        onCancel={() => setPendingDelete(null)}
        onConfirm={confirmDelete}
      />
    </aside>
  )
}

export default ChatSidebar
