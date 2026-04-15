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
