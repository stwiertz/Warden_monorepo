import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockVerifySessionCookie = vi.fn()

vi.mock('@/lib/firebase/admin', () => ({
  adminAuth: {
    verifySessionCookie: (...args: unknown[]) => mockVerifySessionCookie(...args),
  },
}))

const mockPreviewCoupon = vi.fn()

vi.mock('@/lib/stripe/coupons', () => ({
  previewCoupon: (...args: unknown[]) => mockPreviewCoupon(...args),
}))

const mockCreate = vi.fn()

vi.mock('stripe', () => {
  function Stripe(this: { checkout: unknown }) {
    this.checkout = { sessions: { create: (...args: unknown[]) => mockCreate(...args) } }
  }
  return { default: Stripe }
})

function makeRequest(body: unknown, cookie?: string) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (cookie) headers.cookie = cookie
  return new Request('http://localhost/api/checkout/session', {
    method: 'POST',
    headers,
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
}

describe('POST /api/checkout/session', () => {
  const ORIGINAL_ENV = { ...process.env }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    process.env.STRIPE_SECRET_KEY = 'sk_test_mock'
    process.env.STRIPE_PRICE_MONTHLY = 'price_monthly_mock'
    process.env.STRIPE_PRICE_YEARLY = 'price_yearly_mock'
    process.env.NEXT_PUBLIC_APP_URL = 'http://localhost:3000'
    mockCreate.mockResolvedValue({
      id: 'cs_test_mock',
      url: 'https://checkout.stripe.com/c/pay/mock',
    })
    mockPreviewCoupon.mockReset()
  })

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV }
  })

  it('returns 400 on invalid JSON body', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest('not-json', 'session=abc'))
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error.code).toBe('INVALID_REQUEST')
  })

  it('returns 400 on invalid planId', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'weekly' }, 'session=abc'))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_REQUEST')
  })

  it('returns 401 on missing session cookie', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }))
    expect(res.status).toBe(401)
    expect((await res.json()).error.code).toBe('UNAUTHENTICATED')
  })

  it('returns 401 when session cookie verification throws', async () => {
    mockVerifySessionCookie.mockRejectedValue(new Error('bad cookie'))
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=bad'))
    expect(res.status).toBe(401)
    expect((await res.json()).error.code).toBe('UNAUTHENTICATED')
  })

  it('happy path monthly returns 200 with { data: { url } }', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-1', email: 'a@b.co' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body).toEqual({ data: { url: 'https://checkout.stripe.com/c/pay/mock' } })
    expect(mockVerifySessionCookie).toHaveBeenCalledWith('good', true)
    expect(mockCreate).toHaveBeenCalledTimes(1)
    const args = mockCreate.mock.calls[0][0]
    expect(args.mode).toBe('subscription')
    expect(args.line_items).toEqual([{ price: 'price_monthly_mock', quantity: 1 }])
    expect(args.client_reference_id).toBe('user-1')
    expect(args.customer_email).toBe('a@b.co')
    expect(args.metadata).toEqual({ firebase_uid: 'user-1', plan_id: 'monthly' })
    expect(args.subscription_data).toEqual({
      metadata: { firebase_uid: 'user-1', plan_id: 'monthly' },
    })
    expect(args.allow_promotion_codes).toBe(true)
    expect(args.success_url).toContain(
      '/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}',
    )
    expect(args.cancel_url).toContain('/pricing?checkout=canceled')
  })

  it('happy path yearly resolves yearly price', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-2', email: 'y@b.co' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'yearly' }, 'session=good'))
    expect(res.status).toBe(200)
    const args = mockCreate.mock.calls[0][0]
    expect(args.line_items[0].price).toBe('price_yearly_mock')
    expect(args.metadata.plan_id).toBe('yearly')
  })

  it('returns 500 CHECKOUT_FAILED when Stripe throws', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-3' })
    mockCreate.mockRejectedValue(new Error('stripe down'))
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(500)
    expect((await res.json()).error.code).toBe('CHECKOUT_FAILED')
  })

  it('returns 401 when decoded session cookie has no uid claim', async () => {
    mockVerifySessionCookie.mockResolvedValue({ email: 'x@y.co' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(401)
    expect((await res.json()).error.code).toBe('UNAUTHENTICATED')
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('omits customer_email when decoded session cookie has no email', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-no-email' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(200)
    const args = mockCreate.mock.calls[0][0]
    expect('customer_email' in args).toBe(false)
    expect(args.client_reference_id).toBe('user-no-email')
  })

  it('valid couponCode path passes discounts and omits allow_promotion_codes', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-c', email: 'c@b.co' })
    mockPreviewCoupon.mockResolvedValue({
      coupon: {
        code: 'HALF',
        percentOff: 50,
        amountOffCents: null,
        durationInMonths: null,
      },
      promotionCodeId: 'promo_half',
    })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly', couponCode: 'HALF' }, 'session=good'))
    expect(res.status).toBe(200)
    const args = mockCreate.mock.calls[0][0]
    expect(args.discounts).toEqual([{ promotion_code: 'promo_half' }])
    expect('allow_promotion_codes' in args).toBe(false)
    expect(mockPreviewCoupon).toHaveBeenCalledWith('HALF')
  })

  it('previewCoupon throwing during revalidation returns 500 CHECKOUT_FAILED', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-c', email: 'c@b.co' })
    mockPreviewCoupon.mockRejectedValue(new Error('stripe down'))
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly', couponCode: 'ANY' }, 'session=good'))
    expect(res.status).toBe(500)
    expect((await res.json()).error.code).toBe('CHECKOUT_FAILED')
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('invalid couponCode returns 400 COUPON_INVALID and does not call Stripe.create', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-c', email: 'c@b.co' })
    mockPreviewCoupon.mockResolvedValue(null)
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly', couponCode: 'NOPE' }, 'session=good'))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('COUPON_INVALID')
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('no-couponCode path still sends allow_promotion_codes: true', async () => {
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-1', email: 'a@b.co' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(200)
    const args = mockCreate.mock.calls[0][0]
    expect(args.allow_promotion_codes).toBe(true)
    expect('discounts' in args).toBe(false)
    expect(mockPreviewCoupon).not.toHaveBeenCalled()
  })

  it('returns 500 MISSING_STRIPE_PRICE_ID when price env var is absent', async () => {
    delete process.env.STRIPE_PRICE_MONTHLY
    mockVerifySessionCookie.mockResolvedValue({ uid: 'user-4' })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ planId: 'monthly' }, 'session=good'))
    expect(res.status).toBe(500)
    expect((await res.json()).error.code).toBe('MISSING_STRIPE_PRICE_ID')
    expect(mockCreate).not.toHaveBeenCalled()
  })
})
