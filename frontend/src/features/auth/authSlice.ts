import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'

export interface User {
  id: string
  email: string
  name: string
}

interface AuthState {
  user: User | null
  status: 'idle' | 'loading' | 'succeeded' | 'failed'
  error: string | null
}

const initialState: AuthState = {
  user: null,
  status: 'idle',
  error: null,
}

async function parseError(res: Response): Promise<string> {
  const body = await res.json().catch(() => null)
  return body?.detail ?? `Backend responded with ${res.status}`
}

// A 401 here just means "no session yet" — the ordinary logged-out state,
// not a real failure — so it's resolved rather than rejected.
export const fetchCurrentUser = createAsyncThunk<User | null>('auth/fetchCurrentUser', async () => {
  const res = await fetch('/api/me')
  if (res.status === 401) return null
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as User
})

export const login = createAsyncThunk<User, { email: string; password: string }>(
  'auth/login',
  async ({ email, password }) => {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) throw new Error(await parseError(res))
    return (await res.json()) as User
  },
)

export const logout = createAsyncThunk('auth/logout', async () => {
  const res = await fetch('/api/logout', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
})

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchCurrentUser.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.user = action.payload
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.error.message ?? 'Could not check the current session'
      })
      .addCase(login.pending, (state) => {
        state.status = 'loading'
        state.error = null
      })
      .addCase(login.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.user = action.payload
      })
      .addCase(login.rejected, (state, action) => {
        state.status = 'failed'
        state.error = action.error.message ?? 'Could not log in'
      })
      .addCase(logout.fulfilled, (state) => {
        state.status = 'succeeded'
        state.user = null
      })
  },
})

export default authSlice.reducer
