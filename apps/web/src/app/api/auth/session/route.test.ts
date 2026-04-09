import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockVerifyIdToken = vi.fn()
const mockCreateSessionCookie = vi.fn()

vi.mock('@/lib/firebase/admin', () => ({
  adminAuth: {
    verifyIdToken: (...args: unknown[]) => mockVerifyIdToken(...args),
    createSessionCookie: (...args: unknown[]) => mockCreateSessionCookie(...args),
  },
}))

const mockCookiesSet = vi.fn()
const mockCookiesDelete = vi.fn()

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({
    set: mockCookiesSet,
    delete: mockCookiesDelete,
  })),
}))

describe('Session API Route Handler', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('POST /api/auth/session', () => {
    it('creates a session cookie from a valid ID token', async () => {
      const { POST } = await import('./route')

      mockVerifyIdToken.mockResolvedValue({ uid: 'user-123' })
      mockCreateSessionCookie.mockResolvedValue('session-cookie-value')

      const request = new Request('http://localhost/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: 'valid-firebase-id-token' }),
      })

      const response = await POST(request)
      const body = await response.json()

      expect(response.status).toBe(200)
      expect(body).toEqual({ data: { status: 'success' } })
      expect(mockVerifyIdToken).toHaveBeenCalledWith('valid-firebase-id-token')
      expect(mockCreateSessionCookie).toHaveBeenCalledWith(
        'valid-firebase-id-token',
        expect.objectContaining({ expiresIn: expect.any(Number) }),
      )
      expect(mockCookiesSet).toHaveBeenCalledWith(
        'session',
        'session-cookie-value',
        expect.objectContaining({
          httpOnly: true,
          secure: false,
          sameSite: 'lax',
          path: '/',
        }),
      )
    })

    it('rejects requests with missing idToken', async () => {
      const { POST } = await import('./route')

      const request = new Request('http://localhost/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })

      const response = await POST(request)
      const body = await response.json()

      expect(response.status).toBe(400)
      expect(body.error).toBeDefined()
      expect(body.error.code).toBe('INVALID_REQUEST')
    })

    it('rejects requests with non-string idToken', async () => {
      const { POST } = await import('./route')

      const request = new Request('http://localhost/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: 12345 }),
      })

      const response = await POST(request)
      const body = await response.json()

      expect(response.status).toBe(400)
      expect(body.error.code).toBe('INVALID_REQUEST')
    })

    it('returns 401 for invalid ID token', async () => {
      const { POST } = await import('./route')

      mockVerifyIdToken.mockRejectedValue(new Error('Invalid ID token'))

      const request = new Request('http://localhost/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken: 'invalid-token' }),
      })

      const response = await POST(request)
      const body = await response.json()

      expect(response.status).toBe(401)
      expect(body.error.code).toBe('INVALID_TOKEN')
    })
  })

  describe('DELETE /api/auth/session', () => {
    it('clears the session cookie', async () => {
      const { DELETE } = await import('./route')

      const request = new Request('http://localhost/api/auth/session', {
        method: 'DELETE',
      })

      const response = await DELETE(request)
      const body = await response.json()

      expect(response.status).toBe(200)
      expect(body).toEqual({ data: { status: 'success' } })
      expect(mockCookiesDelete).toHaveBeenCalledWith('session')
    })
  })
})
