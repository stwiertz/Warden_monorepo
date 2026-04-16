import 'server-only'

import { withAuth } from '@/lib/firebase/auth'
import { adminDb } from '@/lib/firebase/admin'
import { getStripe } from '@/lib/stripe/server'

export const runtime = 'nodejs'

export async function POST(request: Request) {
  return withAuth(async (session) => {
    try {
      const userRef = adminDb.collection('users').doc(session.uid)
      const snap = await userRef.get()

      if (!snap.exists) {
        return Response.json(
          { error: { code: 'NO_CUSTOMER', message: 'No subscription found to manage' } },
          { status: 404 },
        )
      }

      const data = snap.data()
      const rawCustomerId = data?.stripe_customer_id

      if (!rawCustomerId || typeof rawCustomerId !== 'string') {
        return Response.json(
          { error: { code: 'NO_CUSTOMER', message: 'No subscription found to manage' } },
          { status: 404 },
        )
      }

      const stripeCustomerId = rawCustomerId

      const fromEnv = process.env.NEXT_PUBLIC_APP_URL
      const appUrl =
        fromEnv && fromEnv.length > 0 ? fromEnv.replace(/\/$/, '') : new URL(request.url).origin

      const stripe = getStripe()
      const portalSession = await stripe.billingPortal.sessions.create({
        customer: stripeCustomerId,
        return_url: `${appUrl}/dashboard`,
      })

      return Response.json({ data: { url: portalSession.url } })
    } catch (err) {
      console.error(
        `[subscription/portal ${new Date().toISOString()}] portal session creation failed:`,
        session.uid,
        err,
      )
      return Response.json(
        {
          error: {
            code: 'PORTAL_SESSION_FAILED',
            message: 'Unable to open subscription management',
          },
        },
        { status: 500 },
      )
    }
  })
}
