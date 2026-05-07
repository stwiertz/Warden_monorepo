import { describe, it, expect, vi, beforeEach } from 'vitest'

import { subscriptionResponseSchema } from '@/lib/schemas/subscription'

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
const mockCollection = vi.fn(() => ({ doc: mockDoc }))

vi.mock('@/lib/firebase/admin', () => ({
  adminDb: {
    collection: (...args: unknown[]) => mockCollection(...args),
  },
}))

describe('GET /api/subscription', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockWithAuthOverride = null
  })

  it('returns subscription data for active subscription', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({
        status: 'active',
        plan: 'monthly',
        current_period_end: { seconds: 1735689600 },
        stripe_customer_id: 'cus_abc',
        stripe_subscription_id: 'sub_abc',
      }),
    })

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.data).toEqual({
      status: 'active',
      plan: 'monthly',
      current_period_end: 1735689600,
      stripe_customer_id: 'cus_abc',
      stripe_subscription_id: 'sub_abc',
    })

    const parsed = subscriptionResponseSchema.safeParse(body.data)
    expect(parsed.success).toBe(true)
  })

  it('returns subscription data for canceled subscription', async () => {
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({
        status: 'canceled',
        plan: 'yearly',
        current_period_end: { seconds: 1735689600 },
        stripe_customer_id: 'cus_xyz',
        stripe_subscription_id: 'sub_xyz',
      }),
    })

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.data.status).toBe('canceled')

    const parsed = subscriptionResponseSchema.safeParse(body.data)
    expect(parsed.success).toBe(true)
  })

  it('returns null data when user has no Firestore document', async () => {
    mockGet.mockResolvedValue({ exists: false })

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.data).toBeNull()
  })

  it('returns 500 on Firestore read error', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGet.mockRejectedValue(new Error('Firestore unavailable'))

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(500)

    const body = await res.json()
    expect(body.error.code).toBe('SUBSCRIPTION_FETCH_FAILED')
    expect(body.error.message).toBe('Unable to load subscription data')

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('[dashboard/api'),
      'uid_test_123',
      expect.any(Error),
    )
    consoleSpy.mockRestore()
  })

  it('returns null data when Firestore document has invalid/partial fields', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGet.mockResolvedValue({
      exists: true,
      data: () => ({
        status: 'active',
        // missing plan, current_period_end, stripe_customer_id, stripe_subscription_id
      }),
    })

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.data).toBeNull()

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('[dashboard/api'),
      'uid_test_123',
      expect.any(String),
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

    const { GET } = await import('./route')
    const res = (await GET()) as Response
    expect(res.status).toBe(401)
  })
})
