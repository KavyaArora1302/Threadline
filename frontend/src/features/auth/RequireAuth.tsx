import { useEffect, useRef, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { fetchCurrentUser } from './authSlice'

function RequireAuth({ children }: { children: ReactNode }) {
  const dispatch = useAppDispatch()
  const { user, status } = useAppSelector((state) => state.auth)
  const didInitAuth = useRef(false)

  useEffect(() => {
    // StrictMode runs effects twice in dev — without this guard, a single
    // fresh page load would fire the session check twice.
    if (didInitAuth.current) return
    didInitAuth.current = true
    dispatch(fetchCurrentUser())
  }, [dispatch])

  if (status === 'idle' || status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas text-[13px] text-muted">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

export default RequireAuth
