'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { useAuth } from '@/hooks/useAuth'
import { ctaPrimaryClass } from '@/components/ui/cta-class'
import { getCtaLabel, type Plan } from '@/lib/pricing/plans'

type CheckoutResponse = { data: { url: string } } | { error: { code: string; message: string } }

const GENERIC_CHECKOUT_ERROR = 'Something went wrong — please try again.'

export function PlanCta({ plan }: { plan: Plan }) {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const disabled = loading || pending

  async function handleClick() {
    setErrorMessage(null)

    if (!user) {
      router.push('/auth/sign-in?next=/pricing')
      return
    }

    setPending(true)
    try {
      const res = await fetch('/api/checkout/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ planId: plan.id }),
      })

      if (!res.ok) {
        setErrorMessage(GENERIC_CHECKOUT_ERROR)
        setPending(false)
        return
      }

      const body = (await res.json()) as CheckoutResponse
      if ('data' in body && body.data.url) {
        window.location.assign(body.data.url)
        return
      }
      setErrorMessage(GENERIC_CHECKOUT_ERROR)
      setPending(false)
    } catch {
      setErrorMessage(GENERIC_CHECKOUT_ERROR)
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        className={`${ctaPrimaryClass} w-full`}
      >
        {getCtaLabel(plan)}
      </button>
      {errorMessage && (
        <p role="alert" className="text-destructive text-sm">
          {errorMessage}
        </p>
      )}
    </div>
  )
}
