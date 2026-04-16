import { z } from 'zod/v4'

export const subscriptionResponseSchema = z.object({
  status: z.enum(['active', 'past_due', 'canceled']),
  plan: z.enum(['monthly', 'yearly']),
  current_period_end: z.number(),
  stripe_customer_id: z.string(),
  stripe_subscription_id: z.string(),
})

export type SubscriptionResponse = z.infer<typeof subscriptionResponseSchema>
