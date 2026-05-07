import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import { SignOutButton } from './SignOutButton'

const mockPush = vi.fn()
const mockRefresh = vi.fn()
const mockDestroy = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: mockRefresh }),
}))

vi.mock('@/lib/firebase/session', () => ({
  destroySessionAndRedirect: (...args: unknown[]) => mockDestroy(...args),
}))

describe('SignOutButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the default "Sign out" label', () => {
    render(<SignOutButton />)
    expect(screen.getByRole('button', { name: /sign out/i })).toBeDefined()
  })

  it('renders custom children when provided', () => {
    render(<SignOutButton>Log out</SignOutButton>)
    expect(screen.getByRole('button', { name: /log out/i })).toBeDefined()
  })

  it('calls destroySessionAndRedirect with the router push on click', async () => {
    mockDestroy.mockResolvedValue(undefined)

    render(<SignOutButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(mockDestroy).toHaveBeenCalledWith(mockPush)
    })
  })

  it('shows the loading state and disables the button while signing out', async () => {
    mockDestroy.mockReturnValue(new Promise(() => {}))

    render(<SignOutButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing out/i })).toBeDefined()
      expect(screen.getByRole('button')).toHaveProperty('disabled', true)
    })
  })

  it('shows an inline error and re-enables the button on failure', async () => {
    mockDestroy.mockRejectedValue(new Error('Failed to destroy session'))

    render(<SignOutButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe('Unable to sign out. Please try again.')
    })
    expect(screen.getByRole('button')).toHaveProperty('disabled', false)
  })

  it('does not show an error on successful sign-out', async () => {
    mockDestroy.mockResolvedValue(undefined)

    render(<SignOutButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(mockDestroy).toHaveBeenCalled()
    })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('calls router.refresh() after a successful sign-out to invalidate RSC cache', async () => {
    mockDestroy.mockResolvedValue(undefined)

    render(<SignOutButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(mockRefresh).toHaveBeenCalled()
    })
  })
})
