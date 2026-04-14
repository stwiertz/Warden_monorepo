import 'server-only'

import Stripe from 'stripe'

import type { Plan } from '@/lib/pricing/plans'

const STRIPE_API_VERSION = '2026-03-25.dahlia'

let _stripe: Stripe | null = null

export function getStripe(): Stripe {
  if (_stripe) return _stripe
  const key = process.env.STRIPE_SECRET_KEY
  if (!key) {
    throw new Error('STRIPE_SECRET_KEY is not set in the environment')
  }
  _stripe = new Stripe(key, { apiVersion: STRIPE_API_VERSION })
  return _stripe
}

export function getPlanPriceId(plan: Plan): string | null {
  const value = process.env[plan.stripePriceEnvKey]
  return value && value.length > 0 ? value : null
}
