'use client'

import { useState } from 'react'

import { ctaPrimaryClass } from '@/components/ui/cta-class'
import { useCheckout, type AppliedCoupon } from '@/components/checkout/CheckoutContext'

type CouponResponse = { data: AppliedCoupon } | { error: { code: string; message: string } }

const GENERIC_ERROR = 'Something went wrong — please try again.'
const INVALID_ERROR = 'This coupon is not valid or has expired.'

export function CouponInput() {
  const { coupon, applyCoupon, clearCoupon } = useCheckout()
  const [value, setValue] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const applied = coupon !== null

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (applied) return

    const trimmed = value.trim()
    if (trimmed.length === 0) return

    setError(null)
    setSuccess(null)
    setPending(true)
    try {
      const res = await fetch('/api/checkout/coupon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: trimmed }),
        cache: 'no-store',
      })
      const body = (await res.json()) as CouponResponse

      if (res.ok && 'data' in body) {
        applyCoupon(body.data)
        setSuccess(`Coupon applied: ${body.data.code}`)
        setPending(false)
        return
      }

      if ('error' in body && body.error.code === 'COUPON_INVALID') {
        setError(INVALID_ERROR)
      } else {
        setError(GENERIC_ERROR)
      }
      setPending(false)
    } catch {
      setError(GENERIC_ERROR)
      setPending(false)
    }
  }

  function handleRemove() {
    clearCoupon()
    setValue('')
    setError(null)
    setSuccess(null)
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto mb-6 flex w-full max-w-md flex-col gap-2">
      <h3 className="sr-only">Coupon code</h3>
      <div className="flex flex-row items-stretch gap-2">
        <input
          type="text"
          aria-label="Coupon code"
          name="coupon"
          autoComplete="off"
          spellCheck={false}
          maxLength={64}
          placeholder="e.g. COACH2FREE"
          value={applied ? coupon.code : value}
          disabled={applied || pending}
          onChange={(event) => setValue(event.target.value)}
          className="bg-card border-border text-foreground focus-visible:ring-ring focus-visible:ring-offset-background flex-1 rounded-[6px] border px-3 py-2 text-base focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-70"
        />
        {applied ? (
          <button
            type="button"
            onClick={handleRemove}
            className="text-muted-foreground min-h-11 min-w-11 underline"
          >
            Remove
          </button>
        ) : (
          <button
            type="submit"
            disabled={pending}
            aria-busy={pending}
            className={`${ctaPrimaryClass}`}
          >
            {pending ? 'Applying…' : 'Apply'}
          </button>
        )}
      </div>
      {success && (
        <p role="status" className="text-muted-foreground text-sm">
          {success}
        </p>
      )}
      {error && (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      )}
    </form>
  )
}
