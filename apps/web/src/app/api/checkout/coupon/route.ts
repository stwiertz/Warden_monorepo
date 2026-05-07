import { z } from 'zod/v4'

import { previewCoupon } from '@/lib/stripe/coupons'

export const runtime = 'nodejs'

const bodySchema = z.object({
  code: z.string().trim().min(1).max(64),
})

function envelopeError(code: string, message: string, status: number) {
  return Response.json({ error: { code, message } }, { status })
}

export async function POST(request: Request) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return envelopeError('INVALID_REQUEST', 'Coupon code is required', 400)
  }

  const parsed = bodySchema.safeParse(body)
  if (!parsed.success) {
    return envelopeError('INVALID_REQUEST', 'Coupon code is required', 400)
  }

  const inputCode = parsed.data.code

  let result
  try {
    result = await previewCoupon(inputCode)
  } catch {
    return envelopeError('COUPON_LOOKUP_FAILED', 'Unable to validate coupon', 500)
  }

  if (!result) {
    return envelopeError('COUPON_INVALID', 'This coupon is not valid or has expired', 400)
  }

  return Response.json({
    data: {
      code: inputCode,
      percentOff: result.coupon.percentOff,
      amountOffCents: result.coupon.amountOffCents,
      durationInMonths: result.coupon.durationInMonths,
    },
  })
}
