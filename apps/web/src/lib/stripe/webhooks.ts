import 'server-only'

import type Stripe from 'stripe'

// Self-namespace import: routeEvent calls handlers via `self.handleX` so that
// vi.spyOn(webhooksModule, 'handleX') in webhooks.test.ts actually intercepts
// the intra-module call. Direct `handleX(event)` would bypass the spy because
// of ESM's local-binding resolution. Stories 4.2/4.3 rely on this — do not
// "clean up" to direct calls without also rewriting the spy-based tests.
import * as self from './webhooks'

export async function handleInvoicePaid(event: Stripe.Event): Promise<void> {
  console.log('[webhooks/stripe] invoice.paid received (not yet implemented):', event.id)
}

export async function handleSubscriptionDeleted(event: Stripe.Event): Promise<void> {
  console.log(
    '[webhooks/stripe] customer.subscription.deleted received (not yet implemented):',
    event.id,
  )
}

export async function handlePaymentFailed(event: Stripe.Event): Promise<void> {
  console.log('[webhooks/stripe] invoice.payment_failed received (not yet implemented):', event.id)
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
      console.log('[webhooks/stripe] unhandled event type:', event.type)
      return
  }
}
