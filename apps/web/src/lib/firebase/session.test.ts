import { describe, it, expect, vi, beforeEach } from 'vitest'

import { createSessionAndRedirect, destroySessionAndRedirect } from './session'

const mockSignOut = vi.fn()

vi.mock('firebase/auth', () => ({
  signOut: (...args: unknown[]) => mockSignOut(...args),
}))

vi.mock('@/lib/firebase/client', () => ({
  auth: { name: 'mock-auth' },
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('createSessionAndRedirect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exchanges the id token and redirects to /dashboard on success', async () => {
    const redirect = vi.fn()
    const user = { getIdToken: vi.fn().mockResolvedValue('id-token-123') }
    mockFetch.mockResolvedValue({ ok: true })

    await createSessionAndRedirect(user as never, redirect)

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: 'id-token-123' }),
    })
    expect(redirect).toHaveBeenCalledWith('/dashboard')
  })

  it('throws and does not redirect when session creation fails', async () => {
    const redirect = vi.fn()
    const user = { getIdToken: vi.fn().mockResolvedValue('id-token-123') }
    mockFetch.mockResolvedValue({ ok: false })

    await expect(createSessionAndRedirect(user as never, redirect)).rejects.toThrow(
      'Failed to create session',
    )
    expect(redirect).not.toHaveBeenCalled()
  })
})

describe('destroySessionAndRedirect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls signOut, deletes the session, and redirects to /', async () => {
    const redirect = vi.fn()
    mockSignOut.mockResolvedValue(undefined)
    mockFetch.mockResolvedValue({ ok: true })

    await destroySessionAndRedirect(redirect)

    expect(mockSignOut).toHaveBeenCalledWith({ name: 'mock-auth' })
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', { method: 'DELETE' })
    expect(redirect).toHaveBeenCalledWith('/')
  })

  it('calls signOut before fetch (client state cleared first)', async () => {
    const redirect = vi.fn()
    const order: string[] = []
    mockSignOut.mockImplementation(async () => {
      order.push('signOut')
    })
    mockFetch.mockImplementation(async () => {
      order.push('fetch')
      return { ok: true }
    })

    await destroySessionAndRedirect(redirect)

    expect(order).toEqual(['signOut', 'fetch'])
  })

  it('throws when DELETE response is not ok but signOut was still called', async () => {
    const redirect = vi.fn()
    mockSignOut.mockResolvedValue(undefined)
    mockFetch.mockResolvedValue({ ok: false })

    await expect(destroySessionAndRedirect(redirect)).rejects.toThrow('Failed to destroy session')
    expect(mockSignOut).toHaveBeenCalled()
    expect(redirect).not.toHaveBeenCalled()
  })

  it('still issues DELETE when signOut throws, then propagates the signOut error', async () => {
    const redirect = vi.fn()
    mockSignOut.mockRejectedValue(new Error('signOut failed'))
    mockFetch.mockResolvedValue({ ok: true })

    await expect(destroySessionAndRedirect(redirect)).rejects.toThrow('signOut failed')
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', { method: 'DELETE' })
    expect(redirect).not.toHaveBeenCalled()
  })
})
