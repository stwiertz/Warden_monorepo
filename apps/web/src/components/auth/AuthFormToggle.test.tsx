import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthFormToggle } from './AuthFormToggle'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}))

vi.mock('firebase/auth', () => ({
  signInWithPopup: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: {},
  googleProvider: {},
}))

vi.stubGlobal('fetch', vi.fn())

describe('AuthFormToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders sign-in mode by default', () => {
    render(<AuthFormToggle />)
    expect(screen.getByText('Sign in to Warden')).toBeDefined()
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeDefined()
    expect(screen.getByRole('button', { name: /sign in$/i })).toBeDefined()
    expect(screen.getByText(/don't have an account/i)).toBeDefined()
  })

  it('renders the "or" divider', () => {
    render(<AuthFormToggle />)
    expect(screen.getByText('or')).toBeDefined()
  })

  it('switches to registration mode when toggle is clicked', async () => {
    const user = userEvent.setup()
    render(<AuthFormToggle />)

    await user.click(screen.getByText('Create one'))

    expect(screen.getByText('Create your account')).toBeDefined()
    expect(screen.getByRole('button', { name: /create account/i })).toBeDefined()
    expect(screen.getByText(/already have an account/i)).toBeDefined()
  })

  it('switches back to sign-in mode', async () => {
    const user = userEvent.setup()
    render(<AuthFormToggle />)

    await user.click(screen.getByText('Create one'))
    expect(screen.getByText('Create your account')).toBeDefined()

    await user.click(screen.getByText('Sign in'))
    expect(screen.getByText('Sign in to Warden')).toBeDefined()
  })

  it('shows Google sign-in in both modes', async () => {
    const user = userEvent.setup()
    render(<AuthFormToggle />)

    // Sign-in mode
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeDefined()

    // Register mode
    await user.click(screen.getByText('Create one'))
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeDefined()
  })
})
