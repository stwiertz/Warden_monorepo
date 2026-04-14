import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockPreviewCoupon = vi.fn()

vi.mock('@/lib/stripe/coupons', () => ({
  previewCoupon: (...args: unknown[]) => mockPreviewCoupon(...args),
}))

function makeRequest(body: unknown) {
  return new Request('http://localhost/api/checkout/coupon', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
}

describe('POST /api/checkout/coupon', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  it('returns 400 INVALID_REQUEST on non-JSON body', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest('not-json'))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_REQUEST')
  })

  it('returns 400 INVALID_REQUEST on empty string code', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: '   ' }))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_REQUEST')
  })

  it('returns 400 INVALID_REQUEST when code missing', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest({}))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_REQUEST')
  })

  it('happy path percent-off returns 200 with normalized data', async () => {
    mockPreviewCoupon.mockResolvedValue({
      coupon: {
        code: 'SAVE50',
        percentOff: 50,
        amountOffCents: null,
        durationInMonths: null,
      },
      promotionCodeId: 'promo_1',
    })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'SAVE50' }))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body).toEqual({
      data: {
        code: 'SAVE50',
        percentOff: 50,
        amountOffCents: null,
        durationInMonths: null,
      },
    })
    expect(mockPreviewCoupon).toHaveBeenCalledWith('SAVE50')
  })

  it('happy path amount-off returns 200 with cents', async () => {
    mockPreviewCoupon.mockResolvedValue({
      coupon: {
        code: 'FIVE',
        percentOff: null,
        amountOffCents: 500,
        durationInMonths: null,
      },
      promotionCodeId: 'promo_2',
    })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'FIVE' }))
    expect(res.status).toBe(200)
    expect((await res.json()).data.amountOffCents).toBe(500)
  })

  it('happy path repeating returns durationInMonths', async () => {
    mockPreviewCoupon.mockResolvedValue({
      coupon: {
        code: 'COACH',
        percentOff: 100,
        amountOffCents: null,
        durationInMonths: 3,
      },
      promotionCodeId: 'promo_3',
    })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'COACH' }))
    expect(res.status).toBe(200)
    expect((await res.json()).data.durationInMonths).toBe(3)
  })

  it('preserves the user input casing in the response', async () => {
    mockPreviewCoupon.mockResolvedValue({
      coupon: {
        code: 'mixedCase',
        percentOff: 10,
        amountOffCents: null,
        durationInMonths: null,
      },
      promotionCodeId: 'promo_4',
    })
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'mixedCase' }))
    expect((await res.json()).data.code).toBe('mixedCase')
  })

  it('returns 400 COUPON_INVALID when previewCoupon returns null', async () => {
    mockPreviewCoupon.mockResolvedValue(null)
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'NOPE' }))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('COUPON_INVALID')
  })

  it('returns 500 COUPON_LOOKUP_FAILED when previewCoupon throws', async () => {
    mockPreviewCoupon.mockRejectedValue(new Error('stripe down'))
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ code: 'ANY' }))
    expect(res.status).toBe(500)
    expect((await res.json()).error.code).toBe('COUPON_LOOKUP_FAILED')
  })

  it('does not read session cookie (public endpoint)', async () => {
    mockPreviewCoupon.mockResolvedValue({
      coupon: { code: 'X', percentOff: 10, amountOffCents: null, durationInMonths: null },
      promotionCodeId: 'promo_5',
    })
    const { POST } = await import('./route')
    // No cookie attached; should still succeed
    const res = await POST(makeRequest({ code: 'X' }))
    expect(res.status).toBe(200)
  })
})
