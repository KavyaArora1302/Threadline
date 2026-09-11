import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '../../app/store'

export interface Turn {
  question: string
  answer: string | null
  // Client-side only — the backend never persists or echoes this back.
  image?: string
}

export interface ChatSummary {
  id: string
  title: string
  created_at: string
  model: string
}

export interface ModelInfo {
  id: string
  label: string
  provider: string
  supports_image: boolean
}

interface ChatState {
  status: 'idle' | 'loading' | 'succeeded' | 'failed'
  currentRepo: string
  chats: ChatSummary[]
  models: ModelInfo[]
  activeChatId: string | null
  conversation: Turn[]
  askingChatIds: string[]
  error: string | null
}

const initialState: ChatState = {
  status: 'idle',
  currentRepo: '',
  chats: [],
  models: [],
  activeChatId: null,
  conversation: [],
  askingChatIds: [],
  error: null,
}

interface StateResponse {
  current_repo: string
  chats: ChatSummary[]
  current_chat_id: string
  conversation: Turn[]
}

interface ChatDetail {
  id: string
  title: string
  model: string
  conversation: Turn[]
}

async function parseError(res: Response): Promise<string> {
  const body = await res.json().catch(() => null)
  return body?.detail ?? `Backend responded with ${res.status}`
}

export const fetchState = createAsyncThunk('chat/fetchState', async () => {
  const res = await fetch('/api/state')
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as StateResponse
})

export const askQuestion = createAsyncThunk<
  { turn: Turn; chatId: string },
  { question: string; chatId: string; image?: string }
>('chat/askQuestion', async ({ question, chatId, image }) => {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, chat_id: chatId, image }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const turn = (await res.json()) as Turn
  return { turn, chatId }
})

export const refreshChats = createAsyncThunk('chat/refreshChats', async () => {
  const res = await fetch('/api/chats')
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as { chats: ChatSummary[] }
})

export const selectChat = createAsyncThunk('chat/selectChat', async (chatId: string) => {
  const res = await fetch(`/api/chats/${chatId}`)
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as ChatDetail
})

export const createChat = createAsyncThunk('chat/createChat', async () => {
  const res = await fetch('/api/chats', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as ChatSummary
})

export const renameChat = createAsyncThunk(
  'chat/renameChat',
  async ({ chatId, title }: { chatId: string; title: string }) => {
    const res = await fetch(`/api/chats/${chatId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
    if (!res.ok) throw new Error(await parseError(res))
    return (await res.json()) as ChatSummary
  },
)

export const fetchModels = createAsyncThunk('chat/fetchModels', async () => {
  const res = await fetch('/api/models')
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as { models: ModelInfo[] }
})

export const changeChatModel = createAsyncThunk(
  'chat/changeChatModel',
  async ({ chatId, model }: { chatId: string; model: string }) => {
    const res = await fetch(`/api/chats/${chatId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
    if (!res.ok) throw new Error(await parseError(res))
    return (await res.json()) as ChatSummary
  },
)

// If you delete the chat you're currently looking at, switch to the next
// most recent remaining chat, or start a fresh one if that was the last chat.
export const deleteChat = createAsyncThunk<void, string, { state: RootState }>(
  'chat/deleteChat',
  async (chatId, { dispatch, getState }) => {
    const res = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await parseError(res))

    const wasActive = getState().chat.activeChatId === chatId
    dispatch(chatRemoved(chatId))

    if (wasActive) {
      const remaining = getState().chat.chats
      if (remaining.length > 0) {
        dispatch(selectChat(remaining[0].id))
      } else {
        dispatch(createChat())
      }
    }
  },
)

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    chatRemoved(state, action: PayloadAction<string>) {
      state.chats = state.chats.filter((c) => c.id !== action.payload)
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchState.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(fetchState.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.currentRepo = action.payload.current_repo
        state.chats = action.payload.chats
        state.activeChatId = action.payload.current_chat_id
        state.conversation = action.payload.conversation
      })
      .addCase(fetchState.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.error.message ?? 'Unknown error'
      })
      .addCase(askQuestion.pending, (state, action) => {
        state.askingChatIds.push(action.meta.arg.chatId)
        state.error = null
        // Show the question immediately, before the answer comes back — the
        // null answer is what tells MessageBubble to render it question-only.
        if (state.activeChatId === action.meta.arg.chatId) {
          state.conversation.push({
            question: action.meta.arg.question,
            answer: null,
            image: action.meta.arg.image,
          })
        }
      })
      .addCase(askQuestion.fulfilled, (state, action) => {
        state.askingChatIds = state.askingChatIds.filter((id) => id !== action.payload.chatId)
        if (state.activeChatId === action.payload.chatId) {
          const last = state.conversation[state.conversation.length - 1]
          if (last && last.answer === null) {
            state.conversation[state.conversation.length - 1] = {
              ...action.payload.turn,
              image: last.image,
            }
          } else {
            state.conversation.push(action.payload.turn)
          }
        }
      })
      .addCase(askQuestion.rejected, (state, action) => {
        state.askingChatIds = state.askingChatIds.filter((id) => id !== action.meta.arg.chatId)
        state.error = action.error.message ?? 'Could not get an answer'
        if (state.activeChatId === action.meta.arg.chatId) {
          const last = state.conversation[state.conversation.length - 1]
          if (last && last.answer === null) {
            state.conversation.pop()
          }
        }
      })
      .addCase(refreshChats.fulfilled, (state, action) => {
        state.chats = action.payload.chats
      })
      .addCase(selectChat.fulfilled, (state, action) => {
        state.activeChatId = action.payload.id
        state.conversation = action.payload.conversation
      })
      .addCase(selectChat.rejected, (state, action) => {
        state.error = action.error.message ?? 'Could not load that chat'
      })
      .addCase(createChat.fulfilled, (state, action) => {
        state.chats.unshift(action.payload)
        state.activeChatId = action.payload.id
        state.conversation = []
      })
      .addCase(createChat.rejected, (state, action) => {
        state.error = action.error.message ?? 'Could not start a new chat'
      })
      .addCase(deleteChat.rejected, (state, action) => {
        state.error = action.error.message ?? 'Could not delete that chat'
      })
      .addCase(renameChat.fulfilled, (state, action) => {
        const chat = state.chats.find((c) => c.id === action.payload.id)
        if (chat) chat.title = action.payload.title
      })
      .addCase(renameChat.rejected, (state, action) => {
        state.error = action.error.message ?? 'Could not rename that chat'
      })
      .addCase(fetchModels.fulfilled, (state, action) => {
        state.models = action.payload.models
      })
      .addCase(changeChatModel.fulfilled, (state, action) => {
        const chat = state.chats.find((c) => c.id === action.payload.id)
        if (chat) chat.model = action.payload.model
      })
      .addCase(changeChatModel.rejected, (state, action) => {
        state.error = action.error.message ?? 'Could not change the model'
      })
  },
})

export const { chatRemoved } = chatSlice.actions
export default chatSlice.reducer
