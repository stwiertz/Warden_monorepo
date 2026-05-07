import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

import { HeaderAuthActions } from './HeaderAuthActions'

let mockAuthState = { user: null as unknown, loading: false, error: null }

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockAuthState,
}))

vi.mock('@/components/auth/SignOutButton', () => ({
  SignOutButton: ({ children }: { children?: React.ReactNode }) => (
    <button data-testid="sign-out-button">{children}</button>
  ),
}))

function renderInList(node: React.ReactNode) {
  return render(<ul>{node}</ul>)
}

describe('HeaderAuthActions', () => {
  beforeEach(() => {
    mockAuthState = { user: null, loading: false, error: null }
  })

  it('renders nothing meaningful while loading', () => {
    mockAuthState = { user: null, loading: true, error: null }
    renderInList(<HeaderAuthActions />)
    expect(screen.queryByRole('link', { name: /sign in/i })).toBeNull()
    expect(screen.queryByTestId('sign-out-button')).toBeNull()
  })

  it('renders Home, Pricing, and Sign in links when no user is signed in', () => {
    mockAuthState = { user: null, loading: false, error: null }
    renderInList(<HeaderAuthActions />)

    const homeLink = screen.getByRole('link', { name: /^home$/i })
    expect(homeLink).toBeDefined()
    expect(homeLink.getAttribute('href')).toBe('/')

    const pricingLink = screen.getByRole('link', { name: /^pricing$/i })
    expect(pricingLink).toBeDefined()
    expect(pricingLink.getAttribute('href')).toBe('/pricing')

    const signInLink = screen.getByRole('link', { name: /sign in/i })
    expect(signInLink).toBeDefined()
    expect(signInLink.getAttribute('href')).toBe('/auth/sign-in')
  })

  it('renders Dashboard link and SignOutButton when user is signed in', () => {
    mockAuthState = {
      user: { displayName: 'Jane', email: 'jane@example.com' },
      loading: false,
      error: null,
    }
    renderInList(<HeaderAuthActions />)

    const dashboardLink = screen.getByRole('link', { name: /dashboard/i })
    expect(dashboardLink).toBeDefined()
    expect(dashboardLink.getAttribute('href')).toBe('/dashboard')

    expect(screen.getByTestId('sign-out-button')).toBeDefined()
  })

  it('does not show Pricing or Sign in links when signed in, but keeps Home', () => {
    mockAuthState = {
      user: { displayName: 'Jane', email: 'jane@example.com' },
      loading: false,
      error: null,
    }
    renderInList(<HeaderAuthActions />)
    expect(screen.getByRole('link', { name: /^home$/i })).toBeDefined()
    expect(screen.queryByRole('link', { name: /^pricing$/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /sign in/i })).toBeNull()
  })

  it('does not show Dashboard link when not signed in', () => {
    mockAuthState = { user: null, loading: false, error: null }
    renderInList(<HeaderAuthActions />)
    expect(screen.queryByRole('link', { name: /dashboard/i })).toBeNull()
  })
})
