'use client'

import { useEffect, useState } from 'react'

import { subscriptionResponseSchema, type SubscriptionResponse } from '@/lib/schemas/subscription'

interface UseSubscriptionResult {
  subscription: SubscriptionResponse | null
  loading: boolean
  error: string | null
}

export function useSubscription(): UseSubscriptionResult {
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchSubscription() {
      try {
        const res = await fetch('/api/subscription')
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body?.error?.message || 'Failed to load subscription')
        }
        const body = await res.json()
        if (!cancelled) {
          if (body.data === null) {
            setSubscription(null)
          } else {
            const parsed = subscriptionResponseSchema.safeParse(body.data)
            if (!parsed.success) {
              throw new Error('Invalid subscription data')
            }
            setSubscription(parsed.data)
          }
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load subscription')
          setLoading(false)
        }
      }
    }

    fetchSubscription()
    return () => {
      cancelled = true
    }
  }, [])

  return { subscription, loading, error }
}
