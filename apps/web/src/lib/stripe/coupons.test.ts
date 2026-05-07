import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockList = vi.fn()

vi.mock('stripe', () => {
  function Stripe(this: { promotionCodes: unknown }) {
    this.promotionCodes = { list: (...args: unknown[]) => mockList(...args) }
  }
  return { default: Stripe }
})

describe('previewCoupon', () => {
  const ORIGINAL_ENV = { ...process.env }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    process.env.STRIPE_SECRET_KEY = 'sk_test_mock'
  })

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV }
  })

  async function load() {
    const mod = await import('./coupons')
    return mod.previewCoupon
  }

  it('returns normalized shape on a percent-off hit', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'promo_123',
          active: true,
          expires_at: null,
          promotion: {
            type: 'coupon',
            coupon: {
              valid: true,
              percent_off: 50,
              amount_off: null,
              duration: 'once',
              duration_in_months: null,
            },
          },
        },
      ],
    })
    const previewCoupon = await load()
    const result = await previewCoupon('SAVE50')
    expect(result).toEqual({
      coupon: {
        code: 'SAVE50',
        percentOff: 50,
        amountOffCents: null,
        durationInMonths: null,
      },
      promotionCodeId: 'promo_123',
    })
    expect(mockList).toHaveBeenCalledWith({
      code: 'SAVE50',
      active: true,
      limit: 1,
      expand: ['data.promotion.coupon'],
    })
  })

  it('returns durationInMonths for a repeating coupon', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'promo_456',
          active: true,
          expires_at: null,
          promotion: {
            type: 'coupon',
            coupon: {
              valid: true,
              percent_off: 100,
              amount_off: null,
              duration: 'repeating',
              duration_in_months: 3,
            },
          },
        },
      ],
    })
    const previewCoupon = await load()
    const result = await previewCoupon('COACH3MO')
    expect(result?.coupon.percentOff).toBe(100)
    expect(result?.coupon.durationInMonths).toBe(3)
  })

  it('returns amount_off cents on an amount-off coupon', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'promo_aoff',
          active: true,
          expires_at: null,
          promotion: {
            type: 'coupon',
            coupon: {
              valid: true,
              percent_off: null,
              amount_off: 500,
              duration: 'once',
              duration_in_months: null,
            },
          },
        },
      ],
    })
    const previewCoupon = await load()
    const result = await previewCoupon('FIVEOFF')
    expect(result?.coupon.amountOffCents).toBe(500)
    expect(result?.coupon.percentOff).toBeNull()
  })

  it('returns null when the list is empty', async () => {
    mockList.mockResolvedValue({ data: [] })
    const previewCoupon = await load()
    expect(await previewCoupon('NOPE')).toBeNull()
  })

  it('returns null when promo is inactive', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'p',
          active: false,
          promotion: { type: 'coupon', coupon: { valid: true, percent_off: 10 } },
        },
      ],
    })
    const previewCoupon = await load()
    expect(await previewCoupon('OFF')).toBeNull()
  })

  it('returns null when promo is expired', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'p',
          active: true,
          expires_at: Math.floor(Date.now() / 1000) - 60,
          promotion: { type: 'coupon', coupon: { valid: true, percent_off: 10 } },
        },
      ],
    })
    const previewCoupon = await load()
    expect(await previewCoupon('OLD')).toBeNull()
  })

  it('returns null when the underlying coupon is invalid', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'p',
          active: true,
          promotion: { type: 'coupon', coupon: { valid: false, percent_off: 10 } },
        },
      ],
    })
    const previewCoupon = await load()
    expect(await previewCoupon('BAD')).toBeNull()
  })

  it('returns null when amount_off is 0 (malformed coupon)', async () => {
    mockList.mockResolvedValue({
      data: [
        {
          id: 'p',
          active: true,
          promotion: {
            type: 'coupon',
            coupon: {
              valid: true,
              percent_off: null,
              amount_off: 0,
              duration: 'once',
            },
          },
        },
      ],
    })
    const previewCoupon = await load()
    expect(await previewCoupon('ZERO')).toBeNull()
  })

  it('returns null on empty input without calling Stripe', async () => {
    const previewCoupon = await load()
    expect(await previewCoupon('   ')).toBeNull()
    expect(mockList).not.toHaveBeenCalled()
  })

  it('rethrows when Stripe throws', async () => {
    mockList.mockRejectedValue(new Error('stripe down'))
    const previewCoupon = await load()
    await expect(previewCoupon('ANY')).rejects.toThrow('stripe down')
  })
})
