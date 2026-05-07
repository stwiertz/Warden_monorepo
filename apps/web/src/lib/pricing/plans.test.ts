import { describe, it, expect } from 'vitest'

import {
  PLAN_MONTHLY,
  PLAN_YEARLY,
  PLANS,
  formatEuro,
  getCtaLabel,
  getPeriodLabel,
  getYearlySavings,
} from './plans'

describe('pricing plans', () => {
  it('exports monthly plan at €7.99 with month period', () => {
    expect(PLAN_MONTHLY.priceCents).toBe(799)
    expect(PLAN_MONTHLY.currency).toBe('EUR')
    expect(PLAN_MONTHLY.billingPeriod).toBe('month')
    expect(getPeriodLabel(PLAN_MONTHLY)).toBe('/month')
    expect(getCtaLabel(PLAN_MONTHLY)).toBe('Subscribe monthly')
  })

  it('exports yearly plan at €79.90 with year period', () => {
    expect(PLAN_YEARLY.priceCents).toBe(7990)
    expect(PLAN_YEARLY.currency).toBe('EUR')
    expect(PLAN_YEARLY.billingPeriod).toBe('year')
    expect(getPeriodLabel(PLAN_YEARLY)).toBe('/year')
    expect(getCtaLabel(PLAN_YEARLY)).toBe('Subscribe yearly')
  })

  it('exposes exactly two plans in order: monthly, yearly', () => {
    expect(PLANS).toHaveLength(2)
    expect(PLANS[0]).toBe(PLAN_MONTHLY)
    expect(PLANS[1]).toBe(PLAN_YEARLY)
  })

  it('formats euros with two decimals and € symbol', () => {
    expect(formatEuro(799)).toMatch(/7[.,]99/)
    expect(formatEuro(799)).toContain('€')
    expect(formatEuro(7990)).toMatch(/79[.,]90/)
  })

  it('computes yearly savings as ~€15.98 (17%) against 12× monthly', () => {
    const savings = getYearlySavings()
    // 7.99 * 12 = 95.88 - 79.90 = 15.98
    expect(savings.amountCents).toBe(1598)
    expect(savings.percent).toBe(17)
  })

  it('both plans declare a non-empty stripePriceEnvKey matching STRIPE_PRICE_*', () => {
    expect(PLAN_MONTHLY.stripePriceEnvKey).toMatch(/^STRIPE_PRICE_/)
    expect(PLAN_YEARLY.stripePriceEnvKey).toMatch(/^STRIPE_PRICE_/)
    expect(PLAN_MONTHLY.stripePriceEnvKey).toBe('STRIPE_PRICE_MONTHLY')
    expect(PLAN_YEARLY.stripePriceEnvKey).toBe('STRIPE_PRICE_YEARLY')
  })

  it('getYearlySavings derives from supplied plans, not hardcoded', () => {
    const cheaperMonthly = { ...PLAN_MONTHLY, priceCents: 1000 }
    const cheaperYearly = { ...PLAN_YEARLY, priceCents: 10000 }
    const savings = getYearlySavings(cheaperMonthly, cheaperYearly)
    expect(savings.amountCents).toBe(2000)
    expect(savings.percent).toBe(17)
  })
})
