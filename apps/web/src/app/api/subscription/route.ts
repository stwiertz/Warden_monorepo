import 'server-only'

import { withAuth } from '@/lib/firebase/auth'
import { adminDb } from '@/lib/firebase/admin'
import { subscriptionResponseSchema } from '@/lib/schemas/subscription'

export const runtime = 'nodejs'

export async function GET() {
  return withAuth(async (session) => {
    try {
      const userRef = adminDb.collection('users').doc(session.uid)
      const snap = await userRef.get()

      if (!snap.exists) {
        return Response.json({ data: null }, { status: 200 })
      }

      const data = snap.data()
      const payload = {
        status: data?.status,
        plan: data?.plan,
        current_period_end: data?.current_period_end?.seconds ?? null,
        stripe_customer_id: data?.stripe_customer_id,
        stripe_subscription_id: data?.stripe_subscription_id,
      }

      const parsed = subscriptionResponseSchema.safeParse(payload)
      if (!parsed.success) {
        console.error(
          `[dashboard/api ${new Date().toISOString()}] invalid subscription document:`,
          session.uid,
          parsed.error.message,
        )
        return Response.json({ data: null }, { status: 200 })
      }

      return Response.json({ data: parsed.data })
    } catch (err) {
      console.error(
        `[dashboard/api ${new Date().toISOString()}] subscription fetch failed:`,
        session.uid,
        err,
      )
      return Response.json(
        {
          error: { code: 'SUBSCRIPTION_FETCH_FAILED', message: 'Unable to load subscription data' },
        },
        { status: 500 },
      )
    }
  })
}
