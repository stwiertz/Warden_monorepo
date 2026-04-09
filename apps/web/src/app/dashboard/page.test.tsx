import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DashboardPage from './page'

const mockPush = vi.fn()
const mockSignOut = vi.fn()
let mockAuthState = { user: null as unknown, loading: false, error: null }

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('firebase/auth', () => ({
  signOut: (...args: unknown[]) => mockSignOut(...args),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockAuthState,
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthState = { user: null, loading: false, error: null }
  })

  it('shows loading skeleton when auth is loading', () => {
    mockAuthState = { user: null, loading: true, error: null }
    render(<DashboardPage />)
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  it('redirects to sign-in when user is null and not loading', async () => {
    mockAuthState = { user: null, loading: false, error: null }
    render(<DashboardPage />)

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/auth/sign-in')
    })
  })

  it('displays user info when authenticated', () => {
    mockAuthState = {
      user: { displayName: 'John Doe', email: 'john@example.com' },
      loading: false,
      error: null,
    }
    render(<DashboardPage />)
    expect(screen.getByText('John Doe')).toBeDefined()
    expect(screen.getByText('john@example.com')).toBeDefined()
  })

  it('renders sign out button', () => {
    mockAuthState = {
      user: { displayName: 'John', email: 'john@example.com' },
      loading: false,
      error: null,
    }
    render(<DashboardPage />)
    expect(screen.getByRole('button', { name: /sign out/i })).toBeDefined()
  })

  it('handles sign out flow', async () => {
    mockAuthState = {
      user: { displayName: 'John', email: 'john@example.com' },
      loading: false,
      error: null,
    }
    mockSignOut.mockResolvedValue(undefined)
    mockFetch.mockResolvedValue({ ok: true })

    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }))

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', { method: 'DELETE' })
    })

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/')
    })
  })
})
