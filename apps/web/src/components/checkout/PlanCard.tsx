'use client'

import { Sparkles } from 'lucide-react'

import { PlanCta } from '@/components/checkout/PlanCta'
import { useCheckout } from '@/components/checkout/CheckoutContext'
import { computeDiscountedPrice } from '@/lib/pricing/discount'
import { formatEuro, getPeriodLabel, getYearlySavings, type Plan } from '@/lib/pricing/plans'

const dateFormatter = new Intl.DateTimeFormat('en-IE', { dateStyle: 'long' })

export function PlanCard({ plan }: { plan: Plan }) {
  const { coupon } = useCheckout()
  const headingId = `plan-${plan.id}-name`
  const featured = plan.id === 'yearly'

  const yearlySavings = getYearlySavings()
  const savingsLabel = `Save ${formatEuro(yearlySavings.amountCents)} (~${yearlySavings.percent}%) vs monthly`

  const discount = coupon ? computeDiscountedPrice(plan, coupon) : null

  return (
    <article
      aria-labelledby={headingId}
      className={`bg-card text-card-foreground border-border relative flex flex-col gap-6 rounded-[8px] border p-6 md:p-8 ${
        featured ? 'border-primary ring-primary/30 ring-2' : ''
      }`}
    >
      {featured && (
        <span className="bg-primary text-primary-foreground absolute -top-3 right-6 inline-flex items-center gap-1 rounded-[6px] px-3 py-1 text-xs font-semibold">
          <Sparkles className="size-3.5" aria-hidden="true" />
          Best value
        </span>
      )}
      <div className="flex flex-col gap-2">
        <h3
          id={headingId}
          className="text-foreground text-[1.25rem] font-semibold md:text-[1.5rem]"
        >
          {plan.name}
        </h3>
        <p className="text-muted-foreground text-sm leading-relaxed">{plan.benefits}</p>
      </div>
      <div className="flex flex-col gap-1">
        {discount && (
          <s className="text-muted-foreground text-base line-through">
            {formatEuro(plan.priceCents)}
          </s>
        )}
        <div className="flex items-baseline gap-1">
          <span className="text-foreground text-[2rem] font-extrabold tracking-tight md:text-[2.5rem]">
            {formatEuro(discount ? discount.discountedCents : plan.priceCents)}
          </span>
          <span className="text-muted-foreground text-base">{getPeriodLabel(plan)}</span>
        </div>
        {discount && discount.deferredUntil !== null && (
          <p className="text-muted-foreground text-sm" data-testid="deferred-charge-label">
            First charge on {dateFormatter.format(discount.deferredUntil)}
          </p>
        )}
        {discount && discount.discountedCents === 0 && discount.deferredUntil === null && (
          <p className="text-muted-foreground text-sm" data-testid="free-coupon-label">
            Free with this coupon
          </p>
        )}
      </div>
      {featured && !discount && (
        <p className="text-primary text-sm font-medium" data-testid="savings-label">
          {savingsLabel}
        </p>
      )}
      <PlanCta plan={plan} />
    </article>
  )
}
