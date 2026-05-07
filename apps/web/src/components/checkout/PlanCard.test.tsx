import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'

import { PlanCard } from './PlanCard'
import { CheckoutProvider, type AppliedCoupon } from './CheckoutContext'
import { PLAN_MONTHLY, PLAN_YEARLY } from '@/lib/pricing/plans'

vi.mock('@/components/checkout/PlanCta', () => ({
  PlanCta: ({ plan }: { plan: { id: string } }) => (
    <button type="button" data-testid={`plan-cta-${plan.id}`}>
      cta
    </button>
  ),
}))

function renderCard(plan = PLAN_MONTHLY, initialCoupon?: AppliedCoupon) {
  return render(
    <CheckoutProvider initialCoupon={initialCoupon}>
      <PlanCard plan={plan} />
    </CheckoutProvider>,
  )
}

describe('PlanCard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 15, 12, 0, 0)))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the full price and savings label when no coupon (yearly)', () => {
    renderCard(PLAN_YEARLY)
    const card = screen.getByRole('article', { name: /yearly/i })
    expect(card).toHaveTextContent(/€\s*79[.,]90/)
    expect(screen.getByTestId('savings-label')).toBeInTheDocument()
    expect(screen.queryByTestId('deferred-charge-label')).toBeNull()
  })

  it('renders strikethrough + discounted price when a 50% coupon is applied', () => {
    renderCard(PLAN_MONTHLY, {
      code: 'HALF',
      percentOff: 50,
      amountOffCents: null,
      durationInMonths: null,
    })
    const card = screen.getByRole('article', { name: /monthly/i })
    expect(card).toHaveTextContent(/€\s*7[.,]99/)
    expect(card).toHaveTextContent(/€\s*4[.,]00/)
    const struck = card.querySelector('s')
    expect(struck).not.toBeNull()
  })

  it('renders First charge on ... when a 100% repeating coupon applies', () => {
    renderCard(PLAN_MONTHLY, {
      code: 'COACH3',
      percentOff: 100,
      amountOffCents: null,
      durationInMonths: 3,
    })
    expect(screen.getByTestId('deferred-charge-label')).toHaveTextContent(/first charge on/i)
  })

  it('renders Free with this coupon when 100% forever', () => {
    renderCard(PLAN_MONTHLY, {
      code: 'FOREVER',
      percentOff: 100,
      amountOffCents: null,
      durationInMonths: null,
    })
    expect(screen.getByTestId('free-coupon-label')).toBeInTheDocument()
  })

  it('suppresses the savings label on yearly when a coupon is applied', () => {
    renderCard(PLAN_YEARLY, {
      code: 'HALF',
      percentOff: 50,
      amountOffCents: null,
      durationInMonths: null,
    })
    expect(screen.queryByTestId('savings-label')).toBeNull()
  })
})
