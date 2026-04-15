import 'server-only'

import { FieldValue, Timestamp } from 'firebase-admin/firestore'
import type Stripe from 'stripe'

import { adminDb } from '@/lib/firebase/admin'
import { PLAN_IDS, type PlanId } from '@/lib/pricing/plans'
import { invoicePaidSchema } from '@/lib/schemas/webhook-events'
import { getStripe, retryStripeCall } from '@/lib/stripe/server'

// Self-namespace import: routeEvent calls handlers via `self.handleX` so that
// vi.spyOn(webhooksModule, 'handleX') in webhooks.test.ts actually intercepts
// the intra-module call. Direct `handleX(event)` would bypass the spy because
// of ESM's local-binding resolution. Stories 4.2/4.3 rely on this — do not
// "clean up" to direct calls without also rewriting the spy-based tests.
import * as self from './webhooks'

export async function handleInvoicePaid(event: Stripe.Event): Promise<void> {
  const invoice = event.data.object as Stripe.Invoice
  const parsed = invoicePaidSchema.safeParse(invoice)
  if (!parsed.success) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] invoice.paid payload failed schema validation:`,
      parsed.error.issues,
      event.id,
    )
    throw new Error('invoice.paid schema validation failed')
  }

  const subId = parsed.data.parent.subscription_details.subscription
  const periodEndSeconds = parsed.data.lines.data[0].period.end

  let subscription: Stripe.Subscription
  try {
    subscription = await retryStripeCall(
      () => getStripe().subscriptions.retrieve(subId),
      'subscriptions.retrieve',
    )
  } catch (err) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] subscription retrieve failed after retries:`,
      event.id,
      subId,
      err,
    )
    throw err
  }

  const firebaseUid = subscription.metadata?.firebase_uid
  if (!firebaseUid) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] invoice.paid subscription missing firebase_uid metadata — cannot link to user:`,
      event.id,
      subscription.id,
    )
    throw new Error('invoice.paid subscription missing firebase_uid metadata')
  }

  const planIdRaw = subscription.metadata?.plan_id
  if (!planIdRaw || !(PLAN_IDS as readonly string[]).includes(planIdRaw)) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] invoice.paid subscription has unknown plan_id:`,
      event.id,
      planIdRaw,
    )
    throw new Error('invoice.paid subscription has unknown plan_id')
  }
  const planId = planIdRaw as PlanId

  const customerId =
    typeof subscription.customer === 'string' ? subscription.customer : subscription.customer.id

  const baseFields = {
    status: 'active' as const,
    plan: planId,
    current_period_end: Timestamp.fromMillis(periodEndSeconds * 1000),
    stripe_subscription_id: subscription.id,
    stripe_customer_id: customerId,
    updated_at: FieldValue.serverTimestamp(),
  }

  await adminDb.runTransaction(async (tx) => {
    const userRef = adminDb.collection('users').doc(firebaseUid)
    const snap = await tx.get(userRef)
    if (snap.exists) {
      tx.update(userRef, baseFields)
    } else {
      tx.create(userRef, { ...baseFields, created_at: FieldValue.serverTimestamp() })
    }
  })

  console.log(
    `[webhooks/stripe ${new Date().toISOString()}] invoice.paid processed:`,
    event.id,
    firebaseUid,
    planId,
    new Date(periodEndSeconds * 1000).toISOString(),
  )
}

export async function handleSubscriptionDeleted(event: Stripe.Event): Promise<void> {
  console.log(
    `[webhooks/stripe ${new Date().toISOString()}] customer.subscription.deleted received (handler not yet implemented):`,
    event.id,
  )
}

export async function handlePaymentFailed(event: Stripe.Event): Promise<void> {
  console.log(
    `[webhooks/stripe ${new Date().toISOString()}] invoice.payment_failed received (handler not yet implemented):`,
    event.id,
  )
}

export async function routeEvent(event: Stripe.Event): Promise<void> {
  switch (event.type) {
    case 'invoice.paid':
      await self.handleInvoicePaid(event)
      return
    case 'customer.subscription.deleted':
      await self.handleSubscriptionDeleted(event)
      return
    case 'invoice.payment_failed':
      await self.handlePaymentFailed(event)
      return
    default:
      console.log(`[webhooks/stripe ${new Date().toISOString()}] unhandled event type:`, event.type)
      return
  }
}
