import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AuthProvider } from './AuthContext'
import { useAuth } from '@/hooks/useAuth'

let authStateCallback: ((user: unknown) => void) | null = null
let authErrorCallback: ((error: Error) => void) | null = null
const mockUnsubscribe = vi.fn()

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
}))

vi.mock('firebase/auth', () => ({
  onAuthStateChanged: vi.fn((_, onUser, onError) => {
    authStateCallback = onUser
    authErrorCallback = onError
    return mockUnsubscribe
  }),
}))

function TestConsumer() {
  const { user, loading, error } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? 'logged-in' : 'none'}</span>
      <span data-testid="error">{error ? error.message : 'none'}</span>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    authStateCallback = null
    authErrorCallback = null
    mockUnsubscribe.mockClear()
  })

  it('starts with loading=true and user=null', () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )
    expect(screen.getByTestId('loading').textContent).toBe('true')
    expect(screen.getByTestId('user').textContent).toBe('none')
  })

  it('updates user when auth state changes', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    await act(() => {
      authStateCallback?.({ email: 'test@example.com' })
    })

    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('user').textContent).toBe('logged-in')
  })

  it('sets user to null on sign-out', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    await act(() => {
      authStateCallback?.(null)
    })

    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('user').textContent).toBe('none')
  })

  it('handles auth errors', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    await act(() => {
      authErrorCallback?.(new Error('Auth failed'))
    })

    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('error').textContent).toBe('Auth failed')
  })

  it('throws when useAuth is used outside AuthProvider', () => {
    function OrphanConsumer() {
      useAuth()
      return null
    }

    expect(() => render(<OrphanConsumer />)).toThrow('useAuth must be used within an AuthProvider')
  })

  it('unsubscribes on unmount', () => {
    const { unmount } = render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    )

    unmount()
    expect(mockUnsubscribe).toHaveBeenCalled()
  })
})
