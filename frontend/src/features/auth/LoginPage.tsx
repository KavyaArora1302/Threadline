import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { login } from './authSlice'

function LoginPage() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const { status, error } = useAppSelector((state) => state.auth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const result = await dispatch(login({ email, password }))
    if (login.fulfilled.match(result)) {
      navigate('/', { replace: true })
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-canvas">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-beige-soft p-6 shadow-lg">
        <h1 className="mb-1 text-[17px] font-bold tracking-tight text-ink">Threadline</h1>
        <p className="mb-5 text-[13px] text-muted">Sign in to ask questions about your team's work.</p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13.5px] text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full rounded-md border border-line bg-beige-soft px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-primary"
          />
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-md border border-line bg-beige-soft px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-primary"
          />
          <button
            type="submit"
            disabled={status === 'loading'}
            className="mt-1 w-full rounded-md bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-[#256b4c] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {status === 'loading' ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage
