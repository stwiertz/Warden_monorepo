import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { GoogleSignInButton } from './GoogleSignInButton'

const mockPush = vi.fn()
const mockSignInWithPopup = vi.fn()
const mockGetIdToken = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('firebase/auth', () => ({
  signInWithPopup: (...args: unknown[]) => mockSignInWithPopup(...args),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
  googleProvider: {},
}))

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('GoogleSignInButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the sign-in button', () => {
    render(<GoogleSignInButton />)
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeDefined()
  })

  it('handles successful sign-in flow', async () => {
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithPopup.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ data: { status: 'success' } }) })

    render(<GoogleSignInButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(mockSignInWithPopup).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: 'test-id-token' }),
      })
    })

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('shows loading state during sign-in', async () => {
    mockSignInWithPopup.mockReturnValue(new Promise(() => {})) // Never resolves

    render(<GoogleSignInButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDefined()
      expect(screen.getByRole('button')).toHaveProperty('disabled', true)
    })
  })

  it('displays error when popup is closed', async () => {
    const popupError = new Error('Popup closed')
    Object.assign(popupError, { code: 'auth/popup-closed-by-user' })
    mockSignInWithPopup.mockRejectedValue(popupError)

    render(<GoogleSignInButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe('Sign-in was cancelled.')
    })
  })

  it('displays error when session creation fails', async () => {
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithPopup.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: false, status: 401 })

    render(<GoogleSignInButton />)
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toBe(
        'An error occurred during sign-in. Please try again.',
      )
    })
  })
})
