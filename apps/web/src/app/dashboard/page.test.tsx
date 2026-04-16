import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import DashboardPage from './page'

let mockAuthState = { user: null as unknown, loading: false, error: null }
let mockSubscriptionState = {
  subscription: null as unknown,
  loading: false,
  error: null as string | null,
}
let mockCheckoutParam: string | null = null

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockAuthState,
}))

vi.mock('@/hooks/useSubscription', () => ({
  useSubscription: () => mockSubscriptionState,
}))

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: (key: string) => (key === 'checkout' ? mockCheckoutParam : null),
  }),
}))

vi.mock('@/components/dashboard/SubscriptionCard', () => ({
  SubscriptionCard: (props: {
    userEmail: string | null
    loading: boolean
    error: string | null
  }) => (
    <div
      data-testid="subscription-card"
      data-email={props.userEmail}
      data-loading={props.loading}
      data-error={props.error}
    >
      {props.userEmail && <span>{props.userEmail}</span>}
    </div>
  ),
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
    mockSubscriptionState = { subscription: null, loading: false, error: null }
    mockCheckoutParam = null
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
    const card = screen.getByTestId('subscription-card')
    expect(card.getAttribute('data-email')).toBe('john@example.com')
    expect(screen.getByText('john@example.com')).toBeDefined()
  })

  it('renders the checkout success banner when ?checkout=success', () => {
    mockAuthState = {
      user: { displayName: 'Jane', email: 'jane@example.com' },
      loading: false,
      error: null,
    }
    mockCheckoutParam = 'success'
    render(<DashboardPage />)
    const banner = screen.getByTestId('checkout-success-banner')
    expect(banner).toBeDefined()
    expect(banner.getAttribute('role')).toBe('status')
    expect(banner.getAttribute('aria-live')).toBe('polite')
    expect(banner).toHaveTextContent(/subscription started/i)
    expect(banner).toHaveTextContent(/few seconds/i)
  })

  it('does not render the success banner without the query param', () => {
    mockAuthState = {
      user: { displayName: 'Jane', email: 'jane@example.com' },
      loading: false,
      error: null,
    }
    mockCheckoutParam = null
    render(<DashboardPage />)
    expect(screen.queryByTestId('checkout-success-banner')).toBeNull()
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
