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

  it('renders a "Sign in" link when no user is signed in', () => {
    mockAuthState = { user: null, loading: false, error: null }
    renderInList(<HeaderAuthActions />)
    const link = screen.getByRole('link', { name: /sign in/i })
    expect(link).toBeDefined()
    expect(link.getAttribute('href')).toBe('/auth/sign-in')
  })

  it('renders the SignOutButton when a user is signed in', () => {
    mockAuthState = {
      user: { displayName: 'Jane', email: 'jane@example.com' },
      loading: false,
      error: null,
    }
    renderInList(<HeaderAuthActions />)
    expect(screen.getByTestId('sign-out-button')).toBeDefined()
    expect(screen.queryByRole('link', { name: /sign in/i })).toBeNull()
  })
})
