import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RegistrationForm } from './RegistrationForm'

const mockPush = vi.fn()
const mockCreateUserWithEmailAndPassword = vi.fn()
const mockGetIdToken = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('firebase/auth', () => ({
  createUserWithEmailAndPassword: (...args: unknown[]) =>
    mockCreateUserWithEmailAndPassword(...args),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('RegistrationForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email, password, and confirm password fields', () => {
    render(<RegistrationForm />)
    expect(screen.getByLabelText(/^email$/i)).toBeDefined()
    expect(screen.getByLabelText(/^password$/i)).toBeDefined()
    expect(screen.getByLabelText(/confirm password/i)).toBeDefined()
    expect(screen.getByRole('button', { name: /create account/i })).toBeDefined()
  })

  it('shows validation error for short password', async () => {
    const user = userEvent.setup()
    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'short')
    await user.type(screen.getByLabelText(/confirm password/i), 'short')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters/i)).toBeDefined()
    })
  })

  it('shows validation error for mismatched passwords', async () => {
    const user = userEvent.setup()
    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'different123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeDefined()
    })
  })

  it('handles successful registration flow', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockCreateUserWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: true })

    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(mockCreateUserWithEmailAndPassword).toHaveBeenCalled()
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

  it('shows loading state during registration', async () => {
    const user = userEvent.setup()
    mockCreateUserWithEmailAndPassword.mockReturnValue(new Promise(() => {}))

    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /creating account/i })).toBeDefined()
      expect(screen.getByRole('button')).toHaveProperty('disabled', true)
    })
  })

  it('displays Firebase error for existing email', async () => {
    const user = userEvent.setup()
    const authError = new Error('Email already in use')
    Object.assign(authError, { code: 'auth/email-already-in-use' })
    mockCreateUserWithEmailAndPassword.mockRejectedValue(authError)

    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'existing@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(
        screen.getByText('An account with this email already exists. Try signing in instead.'),
      ).toBeDefined()
    })
  })

  it('clears password fields on Firebase auth error', async () => {
    const user = userEvent.setup()
    const authError = new Error('Email already in use')
    Object.assign(authError, { code: 'auth/email-already-in-use' })
    mockCreateUserWithEmailAndPassword.mockRejectedValue(authError)

    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'existing@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(
        screen.getByText('An account with this email already exists. Try signing in instead.'),
      ).toBeDefined()
    })

    expect(screen.getByLabelText(/^password$/i)).toHaveProperty('value', '')
    expect(screen.getByLabelText(/confirm password/i)).toHaveProperty('value', '')
    expect(screen.getByLabelText(/^email$/i)).toHaveProperty('value', 'existing@example.com')
  })

  it('displays error when session creation fails', async () => {
    const user = userEvent.setup()
    mockGetIdToken.mockResolvedValue('test-id-token')
    mockCreateUserWithEmailAndPassword.mockResolvedValue({
      user: { getIdToken: mockGetIdToken },
    })
    mockFetch.mockResolvedValue({ ok: false, status: 500 })

    render(<RegistrationForm />)

    await user.type(screen.getByLabelText(/^email$/i), 'user@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(
        screen.getByText('An error occurred during registration. Please try again.'),
      ).toBeDefined()
    })
  })
})
