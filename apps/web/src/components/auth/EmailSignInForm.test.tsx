import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailSignInForm } from './EmailSignInForm'

const mockPush = vi.fn()
const mockSignInWithEmailAndPassword = vi.fn()
const mockGetIdToken = vi.fn()
let mockNextParam: string | null = null

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: (key: string) => (key === 'next' ? mockNextParam : null) }),
}))

vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: (...args: unknown[]) => mockSignInWithEmailAndPassword(...args),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('EmailSignInForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockNextParam = null
  })

  it('redirects to safe next param after sign-in', async () => {
    mockNextParam = '/dashboard/settings?tab=billing'
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: true })

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard/settings?tab=billing')
    })
  })

  it('defaults to /dashboard when next is unsafe', async () => {
    mockNextParam = '//evil.com'
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: true })

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('renders email and password fields', () => {
    render(<EmailSignInForm />)
    expect(screen.getByLabelText(/email/i)).toBeDefined()
    expect(screen.getByLabelText(/password/i)).toBeDefined()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeDefined()
  })

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup()
    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'notanemail')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeDefined()
    })
  })

  it('shows validation error for empty password', async () => {
    const user = userEvent.setup()
    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeDefined()
    })
  })

  it('handles successful sign-in flow', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: true })

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockSignInWithEmailAndPassword).toHaveBeenCalled()
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
    const user = userEvent.setup()
    mockSignInWithEmailAndPassword.mockReturnValue(new Promise(() => {}))

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDefined()
      expect(screen.getByRole('button')).toHaveProperty('disabled', true)
    })
  })

  it('displays Firebase error for invalid credentials', async () => {
    const user = userEvent.setup()
    const authError = new Error('Invalid credential')
    Object.assign(authError, { code: 'auth/invalid-credential' })
    mockSignInWithEmailAndPassword.mockRejectedValue(authError)

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeDefined()
    })
  })

  it('clears password field on Firebase auth error', async () => {
    const user = userEvent.setup()
    const authError = new Error('Invalid credential')
    Object.assign(authError, { code: 'auth/invalid-credential' })
    mockSignInWithEmailAndPassword.mockRejectedValue(authError)

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeDefined()
    })

    expect(screen.getByLabelText(/password/i)).toHaveProperty('value', '')
    expect(screen.getByLabelText(/email/i)).toHaveProperty('value', 'user@example.com')
  })

  it('displays error when session creation fails', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockSignInWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: false, status: 401 })

    render(<EmailSignInForm />)

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('An error occurred during sign-in. Please try again.')).toBeDefined()
    })
  })
})
