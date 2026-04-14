export type BillingPeriod = 'month' | 'year'

export type Plan = {
  id: 'monthly' | 'yearly'
  name: string
  priceCents: number
  currency: 'EUR'
  billingPeriod: BillingPeriod
  benefits: string
}

export const PLAN_MONTHLY: Plan = {
  id: 'monthly',
  name: 'Monthly',
  priceCents: 799,
  currency: 'EUR',
  billingPeriod: 'month',
  benefits: 'Full access to session review, clip export, and minimap analysis.',
}

export const PLAN_YEARLY: Plan = {
  id: 'yearly',
  name: 'Yearly',
  priceCents: 7990,
  currency: 'EUR',
  billingPeriod: 'year',
  benefits: 'Everything in Monthly, billed once per year.',
}

export const PLANS: readonly Plan[] = [PLAN_MONTHLY, PLAN_YEARLY]

const euroFormatter = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
})

export function formatEuro(priceCents: number): string {
  return euroFormatter.format(priceCents / 100)
}

export function getPeriodLabel(plan: Plan): string {
  return `/${plan.billingPeriod}`
}

export function getCtaLabel(plan: Plan): string {
  return `Subscribe ${plan.name.toLowerCase()}`
}

export type YearlySavings = {
  amountCents: number
  percent: number
}

export function getYearlySavings(
  monthly: Plan = PLAN_MONTHLY,
  yearly: Plan = PLAN_YEARLY,
): YearlySavings {
  const twelveMonthsCents = monthly.priceCents * 12
  const amountCents = twelveMonthsCents - yearly.priceCents
  const percent = Math.round((amountCents / twelveMonthsCents) * 100)
  return { amountCents, percent }
}
