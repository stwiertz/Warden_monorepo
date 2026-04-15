import { FieldValue } from 'firebase-admin/firestore'
import type Stripe from 'stripe'

import { adminDb } from '@/lib/firebase/admin'
import { getStripe } from '@/lib/stripe/server'
import { routeEvent } from '@/lib/stripe/webhooks'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function envelopeError(code: string, message: string, status: number) {
  return Response.json({ error: { code, message } }, { status })
}

export async function POST(request: Request) {
  const signature = request.headers.get('stripe-signature')
  if (!signature) {
    return envelopeError('INVALID_SIGNATURE', 'Missing stripe-signature header', 400)
  }

  const secret = process.env.STRIPE_WEBHOOK_SECRET
  if (!secret) {
    console.error(`[webhooks/stripe ${new Date().toISOString()}] STRIPE_WEBHOOK_SECRET is not set`)
    return envelopeError('WEBHOOK_NOT_CONFIGURED', 'Webhook handler is not configured', 500)
  }

  const rawBody = await request.text()

  let event: Stripe.Event
  try {
    event = getStripe().webhooks.constructEvent(rawBody, signature, secret)
  } catch (err) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] signature verification failed:`,
      err,
    )
    return envelopeError('INVALID_SIGNATURE', 'Signature verification failed', 400)
  }

  try {
    const alreadyProcessed = await adminDb.runTransaction(async (tx) => {
      const ref = adminDb.collection('stripe_events').doc(event.id)
      const snap = await tx.get(ref)
      if (snap.exists) return true
      tx.create(ref, {
        event_id: event.id,
        event_type: event.type,
        received_at: FieldValue.serverTimestamp(),
        api_version: event.api_version,
        livemode: event.livemode,
      })
      return false
    })

    if (alreadyProcessed) {
      console.log(
        `[webhooks/stripe ${new Date().toISOString()}] duplicate event skipped:`,
        event.id,
      )
      return Response.json({ data: { received: true, duplicate: true } })
    }

    await routeEvent(event)
    return Response.json({
      data: {
        received: true,
        duplicate: false,
        eventId: event.id,
        eventType: event.type,
      },
    })
  } catch (err) {
    console.error(
      `[webhooks/stripe ${new Date().toISOString()}] routing failed for event:`,
      event.id,
      event.type,
      err,
    )
    // return 200 to stop Stripe retries; event is recorded in stripe_events for manual replay
    return Response.json({
      data: {
        received: true,
        duplicate: false,
        routingError: true,
        eventId: event.id,
      },
    })
  }
}
