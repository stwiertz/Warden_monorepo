import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardPage from './page'

let mockAuthState = { user: null as unknown, loading: false, error: null }

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockAuthState,
}))

vi.mock('@/components/auth/SignOutButton', () => ({
  SignOutButton: (props: { variant?: string }) => (
    <button data-testid="sign-out-button" data-variant={props.variant}>
      Sign out
    </button>
  ),
}))

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

  it('shows loading skeleton when user is null (pre-hydration)', () => {
    mockAuthState = { user: null, loading: false, error: null }
    render(<DashboardPage />)
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
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

  it('renders SignOutButton with outline variant', () => {
    mockAuthState = {
      user: { displayName: 'John', email: 'john@example.com' },
      loading: false,
      error: null,
    }
    render(<DashboardPage />)
    const button = screen.getByTestId('sign-out-button')
    expect(button).toBeDefined()
    expect(button.getAttribute('data-variant')).toBe('outline')
  })
})
