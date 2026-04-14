import type { Metadata } from 'next'
import { Sparkles } from 'lucide-react'

import { PlanCta } from '@/components/checkout/PlanCta'
import {
  PLAN_MONTHLY,
  PLAN_YEARLY,
  formatEuro,
  getPeriodLabel,
  getYearlySavings,
  type Plan,
} from '@/lib/pricing/plans'

export const metadata: Metadata = {
  title: 'Pricing — Warden',
  description:
    'Simple, honest pricing for Warden. Choose a monthly or yearly plan and get full access to session review, clip export, and minimap analysis.',
  openGraph: {
    title: 'Pricing — Warden',
    description:
      'Simple, honest pricing for Warden. Choose a monthly or yearly plan and get full access to session review, clip export, and minimap analysis.',
    type: 'website',
    locale: 'en_US',
    siteName: 'Warden',
  },
}

const yearlySavings = getYearlySavings()
const savingsLabel = `Save ${formatEuro(yearlySavings.amountCents)} (~${yearlySavings.percent}%) vs monthly`

type PricingPageProps = {
  searchParams?: Promise<{ checkout?: string }>
}

export default async function PricingPage({ searchParams }: PricingPageProps) {
  const resolved = (await searchParams) ?? {}
  const canceled = resolved.checkout === 'canceled'

  return (
    <div className="flex flex-1 flex-col">
      <section className="mx-auto flex w-full max-w-5xl flex-col items-center gap-4 px-4 py-8 text-center md:px-8 md:py-12">
        <h1 className="text-foreground max-w-2xl text-[2rem] leading-[1.2] font-extrabold tracking-tight md:text-[3rem]">
          Simple, honest pricing
        </h1>
        <p className="text-muted-foreground max-w-xl text-base leading-relaxed md:text-lg">
          One plan, two billing options. Full access to every Warden feature — no tiers, no
          surprises.
        </p>
      </section>

      <section
        aria-labelledby="plans-heading"
        className="mx-auto w-full max-w-5xl px-4 py-8 md:px-8 md:py-12"
      >
        <h2 id="plans-heading" className="sr-only">
          Subscription plans
        </h2>
        {canceled && (
          <p
            data-testid="checkout-canceled-banner"
            className="text-muted-foreground border-border mb-6 rounded-[6px] border px-4 py-3 text-sm"
          >
            Checkout canceled — you can try again anytime.
          </p>
        )}
        <div className="grid gap-6 md:grid-cols-2">
          <PlanCard plan={PLAN_MONTHLY} />
          <PlanCard plan={PLAN_YEARLY} />
        </div>
      </section>
    </div>
  )
}

function PlanCard({ plan }: { plan: Plan }) {
  const headingId = `plan-${plan.id}-name`
  const featured = plan.id === 'yearly'
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
      <div className="flex items-baseline gap-1">
        <span className="text-foreground text-[2rem] font-extrabold tracking-tight md:text-[2.5rem]">
          {formatEuro(plan.priceCents)}
        </span>
        <span className="text-muted-foreground text-base">{getPeriodLabel(plan)}</span>
      </div>
      {featured && (
        <p className="text-primary text-sm font-medium" data-testid="savings-label">
          {savingsLabel}
        </p>
      )}
      <PlanCta plan={plan} />
    </article>
  )
}
