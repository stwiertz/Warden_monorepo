import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockVerifySessionCookie = vi.fn()

vi.mock('@/lib/firebase/admin', () => ({
  adminAuth: {
    verifySessionCookie: (...args: unknown[]) => mockVerifySessionCookie(...args),
  },
}))

const mockCookiesGet = vi.fn()

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({
    get: mockCookiesGet,
  })),
}))

describe('auth helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('requireSession', () => {
    it('returns uid and email on valid session cookie', async () => {
      const { requireSession } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'valid-cookie' })
      mockVerifySessionCookie.mockResolvedValue({ uid: 'abc', email: 'x@y.z' })

      const session = await requireSession()

      expect(session).toEqual({ uid: 'abc', email: 'x@y.z' })
      expect(mockVerifySessionCookie).toHaveBeenCalledWith('valid-cookie', true)
    })

    it('throws UnauthorizedError NO_SESSION when cookie absent', async () => {
      const { requireSession, UnauthorizedError } = await import('./auth')
      mockCookiesGet.mockReturnValue(undefined)

      await expect(requireSession()).rejects.toMatchObject({
        name: 'UnauthorizedError',
        code: 'NO_SESSION',
      })
      await expect(requireSession()).rejects.toBeInstanceOf(UnauthorizedError)
    })

    it('throws UnauthorizedError SESSION_REVOKED on auth/session-cookie-revoked', async () => {
      const { requireSession } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'revoked-cookie' })
      const fbErr = Object.assign(new Error('Firebase session revoked'), {
        code: 'auth/session-cookie-revoked',
      })
      mockVerifySessionCookie.mockRejectedValue(fbErr)

      await expect(requireSession()).rejects.toMatchObject({ code: 'SESSION_REVOKED' })
      await expect(requireSession()).rejects.toMatchObject({ cause: fbErr })
    })

    it('throws UnauthorizedError SESSION_EXPIRED on auth/session-cookie-expired', async () => {
      const { requireSession } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'expired-cookie' })
      mockVerifySessionCookie.mockRejectedValue(
        Object.assign(new Error('expired'), { code: 'auth/session-cookie-expired' }),
      )

      await expect(requireSession()).rejects.toMatchObject({ code: 'SESSION_EXPIRED' })
    })

    it('throws UnauthorizedError UNAUTHORIZED on unknown verify failure', async () => {
      const { requireSession } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'bad-cookie' })
      mockVerifySessionCookie.mockRejectedValue(
        Object.assign(new Error('malformed'), { code: 'auth/argument-error' }),
      )

      await expect(requireSession()).rejects.toMatchObject({ code: 'UNAUTHORIZED' })
    })
  })

  describe('getSession', () => {
    it('returns null instead of throwing when cookie absent', async () => {
      const { getSession } = await import('./auth')
      mockCookiesGet.mockReturnValue(undefined)

      await expect(getSession()).resolves.toBeNull()
    })

    it('returns session on valid cookie', async () => {
      const { getSession } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'valid-cookie' })
      mockVerifySessionCookie.mockResolvedValue({ uid: 'abc', email: 'x@y.z' })

      await expect(getSession()).resolves.toEqual({ uid: 'abc', email: 'x@y.z' })
    })
  })

  describe('withAuth', () => {
    it('invokes handler with session on success', async () => {
      const { withAuth } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'valid-cookie' })
      mockVerifySessionCookie.mockResolvedValue({ uid: 'abc', email: 'x@y.z' })

      const handler = vi.fn().mockResolvedValue('handler-result')
      const result = await withAuth(handler)

      expect(handler).toHaveBeenCalledWith({ uid: 'abc', email: 'x@y.z' })
      expect(result).toBe('handler-result')
    })

    it('returns 401 Response on UnauthorizedError', async () => {
      const { withAuth } = await import('./auth')
      mockCookiesGet.mockReturnValue(undefined)

      const handler = vi.fn()
      const result = await withAuth(handler)

      expect(handler).not.toHaveBeenCalled()
      expect(result).toBeInstanceOf(Response)
      const res = result as Response
      expect(res.status).toBe(401)
      const body = await res.json()
      expect(body).toEqual({
        error: { code: 'NO_SESSION', message: 'Authentication required' },
      })
    })

    it('rethrows non-auth errors', async () => {
      const { withAuth } = await import('./auth')
      mockCookiesGet.mockReturnValue({ value: 'valid-cookie' })
      mockVerifySessionCookie.mockResolvedValue({ uid: 'abc', email: 'x@y.z' })

      const handler = vi.fn().mockRejectedValue(new Error('internal boom'))

      await expect(withAuth(handler)).rejects.toThrow('internal boom')
    })
  })
})
