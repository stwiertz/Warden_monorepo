import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('server-only', () => ({}))

let mockWithAuthOverride: (() => Promise<Response>) | null = null

vi.mock('@/lib/firebase/auth', () => ({
  withAuth: (handler: (session: { uid: string; email: string }) => Promise<Response>) => {
    if (mockWithAuthOverride) return mockWithAuthOverride()
    return handler({ uid: 'uid_test_123', email: 'test@example.com' })
  },
}))

const mockGet = vi.fn()
const mockDoc = vi.fn(() => ({ get: mockGet }))
const mockCollection = vi.fn((..._args: unknown[]) => ({ doc: mockDoc }))

vi.mock('@/lib/firebase/admin', () => ({
  adminDb: {
    collection: (...args: unknown[]) => mockCollection(...args),
  },
}))

const mockPortalSessionsCreate = vi.fn()

vi.mock('@/lib/stripe/server', () => ({
  getStripe: () => ({
    billingPortal: {
      sessions: {
        create: mockPortalSessionsCreate,
      },
    },
  }),
}))

const TEST_REQUEST = new Request('http://localhost:3000/api/subscription/portal', {
  method: 'POST',
})

describe('POST /api/subscription/portal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockWithAuthOverride = null
  })

  it('returns portal URL for user with stripe_customer_id', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ stripe_customer_id: 'cus_abc' }),
    })
    mockPortalSessionsCreate.mockResolvedValue({
      url: 'https://billing.stripe.com/session/test_123',
    })

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.data.url).toBe('https://billing.stripe.com/session/test_123')

    expect(mockPortalSessionsCreate).toHaveBeenCalledWith({
      customer: 'cus_abc',
      return_url: expect.stringContaining('/dashboard'),
    })
  })

  it('passes correct customer to Stripe', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ stripe_customer_id: 'cus_xyz_789' }),
    })
    mockPortalSessionsCreate.mockResolvedValue({
      url: 'https://billing.stripe.com/session/test_456',
    })

    const { POST } = await import('./route')
    await POST(TEST_REQUEST)

    expect(mockPortalSessionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ customer: 'cus_xyz_789' }),
    )
  })

  it('returns return_url ending with /dashboard', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ stripe_customer_id: 'cus_abc' }),
    })
    mockPortalSessionsCreate.mockResolvedValue({
      url: 'https://billing.stripe.com/session/test',
    })

    const { POST } = await import('./route')
    await POST(TEST_REQUEST)

    const call = mockPortalSessionsCreate.mock.calls[0][0]
    expect(call.return_url).toMatch(/\/dashboard$/)
  })

  it('returns 404 when Firestore document does not exist', async () => {
    mockGet.mockResolvedValue({ exists: false })

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(404)

    const body = await res.json()
    expect(body.error.code).toBe('NO_CUSTOMER')
  })

  it('returns 404 when stripe_customer_id is missing from document', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ status: 'active' }),
    })

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(404)

    const body = await res.json()
    expect(body.error.code).toBe('NO_CUSTOMER')
  })

  it('returns 404 when stripe_customer_id is not a string', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ stripe_customer_id: 12345 }),
    })

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(404)

    const body = await res.json()
    expect(body.error.code).toBe('NO_CUSTOMER')
  })

  it('returns 500 when Stripe API throws', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({ stripe_customer_id: 'cus_abc' }),
    })
    mockPortalSessionsCreate.mockRejectedValue(new Error('Stripe connection error'))

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(500)

    const body = await res.json()
    expect(body.error.code).toBe('PORTAL_SESSION_FAILED')

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('[subscription/portal'),
      'uid_test_123',
      expect.any(Error),
    )
    consoleSpy.mockRestore()
  })

  it('returns 401 when unauthenticated', async () => {
    mockWithAuthOverride = async () => {
      return Response.json(
        { error: { code: 'NO_SESSION', message: 'Authentication required' } },
        { status: 401 },
      )
    }

    const { POST } = await import('./route')
    const res = (await POST(TEST_REQUEST)) as Response
    expect(res.status).toBe(401)
  })
})
