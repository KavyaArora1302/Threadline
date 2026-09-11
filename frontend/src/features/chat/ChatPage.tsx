import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type FormEvent,
} from 'react'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  askQuestion,
  changeChatModel,
  createChat,
  fetchModels,
  fetchState,
  refreshChats,
  selectChat,
} from './chatSlice'
import ChatSidebar from './ChatSidebar'
import MessageBubble from './MessageBubble'
import ModelPicker from './ModelPicker'

const MAX_IMAGE_BYTES = 5 * 1024 * 1024
// Kept in sessionStorage (not localStorage) so it survives a page refresh
// within the same tab, but a genuinely fresh visit (new tab, or the tab was
// closed) starts on a new chat instead of jumping back into the last one.
const ACTIVE_CHAT_KEY = 'threadline:activeChatId'

function PaperclipIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.75}
      stroke="currentColor"
      className="h-[18px] w-[18px]"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 002.112 2.13"
      />
    </svg>
  )
}

function XMarkIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.75}
      stroke="currentColor"
      className="h-3.5 w-3.5"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function ChatPage() {
  const dispatch = useAppDispatch()
  const { status, conversation, askingChatIds, activeChatId, chats, models, error } = useAppSelector(
    (state) => state.chat,
  )
  const asking = activeChatId !== null && askingChatIds.includes(activeChatId)
  const activeChat = chats.find((c) => c.id === activeChatId)
  const [question, setQuestion] = useState('')
  const [attachedImage, setAttachedImage] = useState<string | null>(null)
  const [attachedImageName, setAttachedImageName] = useState<string | null>(null)
  const [attachError, setAttachError] = useState<string | null>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const didInitChat = useRef(false)

  useEffect(() => {
    // StrictMode runs effects twice in dev — without this guard, a single
    // fresh page load would fire this init logic twice and create two
    // duplicate empty chats instead of one.
    if (didInitChat.current) return
    didInitChat.current = true

    // Snapshot this *before* fetchState resolves — its own fulfilled reducer
    // sets activeChatId to the server's default, which the effect below
    // immediately persists to sessionStorage. Reading it after that write
    // would make every fresh visit look like a restored session.
    const savedId = sessionStorage.getItem(ACTIVE_CHAT_KEY)
    dispatch(fetchModels())
    ;(async () => {
      const state = await dispatch(fetchState()).unwrap()
      const savedChatStillExists = !!savedId && state.chats.some((c) => c.id === savedId)
      // fetchState bootstraps a fresh empty chat when the whole app has never
      // had one — if that's what we just got, it's already the right chat to
      // land on and creating another would just leave a duplicate empty chat.
      const alreadyOnFreshEmptyChat = state.chats.length === 1 && state.conversation.length === 0

      if (savedChatStillExists) {
        dispatch(selectChat(savedId!))
      } else if (!alreadyOnFreshEmptyChat) {
        dispatch(createChat())
      }
    })()
  }, [dispatch])

  useEffect(() => {
    if (activeChatId) sessionStorage.setItem(ACTIVE_CHAT_KEY, activeChatId)
  }, [activeChatId])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [conversation, asking])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || asking || !activeChatId) return
    const image = attachedImage ?? undefined
    setQuestion('')
    setAttachedImage(null)
    setAttachedImageName(null)
    await dispatch(askQuestion({ question: q, chatId: activeChatId, image }))
    dispatch(refreshChats())
  }

  function attachImageFile(file: File) {
    if (!file.type.startsWith('image/')) {
      setAttachError('Please attach an image file.')
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setAttachError('Image must be smaller than 5MB.')
      return
    }
    setAttachError(null)
    const reader = new FileReader()
    reader.onload = () => {
      setAttachedImage(reader.result as string)
      setAttachedImageName(file.name || 'Pasted image')
    }
    reader.readAsDataURL(file)
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    attachImageFile(file)
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    const item = Array.from(e.clipboardData.items).find((it) => it.type.startsWith('image/'))
    if (!item) return
    const file = item.getAsFile()
    if (!file) return
    e.preventDefault()
    attachImageFile(file)
  }

  function handleRemoveImage() {
    setAttachedImage(null)
    setAttachedImageName(null)
  }

  return (
    <div className="flex h-screen bg-canvas">
      <ChatSidebar />
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-beige-soft px-6 py-3.5">
          <h2 className="truncate text-[14.5px] font-semibold text-ink">{activeChat?.title}</h2>
          {activeChat && models.length > 0 && (
            <ModelPicker
              models={models}
              selectedId={activeChat.model}
              onChange={(model) =>
                activeChatId && dispatch(changeChatModel({ chatId: activeChatId, model }))
              }
            />
          )}
        </header>

        {error && (
          <div className="mx-6 mt-3 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13.5px] text-red-700">
            {error}
          </div>
        )}

        <div ref={threadRef} className="flex-1 overflow-y-auto px-6 pb-2 pt-6">
          <div className="mx-auto flex max-w-[720px] flex-col gap-[18px]">
            {status === 'loading' && conversation.length === 0 ? (
              <p className="m-auto text-sm text-muted">Loading…</p>
            ) : conversation.length === 0 ? (
              <div className="m-auto max-w-[420px] text-center text-sm leading-relaxed text-muted">
                <p className="text-base font-bold text-ink">Ask anything about your team's work.</p>
                <p className="mt-1">
                  Threadline answers using your real GitHub commits, Jira tickets, and Slack
                  messages.
                </p>
              </div>
            ) : (
              conversation.map((turn, i) => <MessageBubble key={i} turn={turn} />)
            )}
            {asking && (
              <div className="flex justify-start">
                <div className="max-w-[92%] rounded-[14px] rounded-bl-[4px] border border-line bg-beige-soft px-4 py-2.5 text-[14.5px] text-muted">
                  Thinking…
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-line bg-beige-soft px-6 pb-5 pt-3.5">
          <div className="mx-auto max-w-[720px]">
            {attachError && <p className="mb-1.5 text-[12.5px] text-red-600">{attachError}</p>}
            {attachedImage && (
              <div className="mb-2 flex items-center gap-2 rounded-lg border border-line bg-beige px-2.5 py-2">
                <img
                  src={attachedImage}
                  alt={attachedImageName ?? 'Attached image'}
                  className="h-10 w-10 rounded object-cover"
                />
                <span className="flex-1 truncate text-[12.5px] text-muted">
                  {attachedImageName}
                </span>
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  aria-label="Remove attached image"
                  className="rounded p-1 text-muted hover:bg-line hover:text-ink"
                >
                  <XMarkIcon />
                </button>
              </div>
            )}
            <form
              onSubmit={handleSubmit}
              className="flex gap-2 rounded-[10px] border border-line bg-beige p-2"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={asking}
                title="Attach an image"
                aria-label="Attach an image"
                className="rounded-md px-2.5 text-muted hover:bg-line hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
              >
                <PaperclipIcon />
              </button>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onPaste={handlePaste}
                placeholder="Ask anything about your team's code, tickets, or discussions..."
                autoFocus
                autoComplete="off"
                className="flex-1 bg-transparent px-3 py-2.5 text-[14.5px] text-ink outline-none placeholder:text-muted"
              />
              <button
                type="submit"
                disabled={asking}
                className="rounded-md bg-primary px-5 text-sm font-semibold text-white hover:bg-[#256b4c] disabled:cursor-not-allowed disabled:opacity-60"
              >
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatPage
