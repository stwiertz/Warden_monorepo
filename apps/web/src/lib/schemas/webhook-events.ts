import { z } from 'zod/v4'

// Stripe API version 2026-03-25.dahlia removed top-level `invoice.subscription`.
// The subscription id now lives at `invoice.parent.subscription_details.subscription`
// (see node_modules/stripe/cjs/resources/Invoices.d.ts — `Invoice.parent` +
// `Parent.SubscriptionDetails.subscription`). This schema reflects that shape.
export const invoicePaidSchema = z.object({
  customer: z.string().min(1),
  parent: z.object({
    subscription_details: z.object({
      subscription: z.string().min(1),
    }),
  }),
  lines: z.object({
    data: z
      .array(
        z.object({
          period: z.object({
            end: z.number().int().positive(),
          }),
        }),
      )
      .min(1),
  }),
})

export type InvoicePaidPayload = z.infer<typeof invoicePaidSchema>

export const subscriptionDeletedSchema = z.object({
  id: z.string().min(1),
  customer: z.union([z.string().min(1), z.object({ id: z.string().min(1) })]),
  metadata: z.record(z.string(), z.string()).optional(),
})

export type SubscriptionDeletedPayload = z.infer<typeof subscriptionDeletedSchema>

// payment_failed reuses the dahlia `parent.subscription_details.subscription`
// nesting documented on invoicePaidSchema above — do NOT regress to a top-level
// `subscription` field (Story 4.2 fixed this on live smoke).
export const paymentFailedSchema = z.object({
  customer: z.string().min(1),
  parent: z.object({
    subscription_details: z.object({
      subscription: z.string().min(1),
    }),
  }),
})

export type PaymentFailedPayload = z.infer<typeof paymentFailedSchema>
