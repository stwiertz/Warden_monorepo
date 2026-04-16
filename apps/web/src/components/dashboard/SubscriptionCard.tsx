'use client'

import { useState } from 'react'
import Link from 'next/link'

import type { SubscriptionResponse } from '@/lib/schemas/subscription'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

interface SubscriptionCardProps {
  subscription: SubscriptionResponse | null
  loading: boolean
  error: string | null
  userEmail: string | null
}

const STATUS_CONFIG = {
  active: {
    label: 'Active',
    className: 'bg-green-500/15 text-green-500 border-transparent',
    dateLabel: 'Next payment',
  },
  past_due: {
    label: 'Past due',
    className: 'bg-amber-500/15 text-amber-500 border-transparent',
    dateLabel: 'Payment due',
  },
  canceled: {
    label: 'Canceled',
    variant: 'secondary' as const,
    dateLabel: 'Access until',
  },
} as const

function getPlanLabel(plan: 'monthly' | 'yearly'): string {
  return plan === 'monthly' ? 'Monthly' : 'Yearly'
}

function formatDate(unixSeconds: number): string {
  return new Intl.DateTimeFormat('en-GB', { dateStyle: 'long', timeZone: 'UTC' }).format(
    new Date(unixSeconds * 1000),
  )
}

export function SubscriptionCard({
  subscription,
  loading,
  error,
  userEmail,
}: SubscriptionCardProps) {
  const [portalLoading, setPortalLoading] = useState(false)
  const [portalError, setPortalError] = useState<string | null>(null)

  async function handleManageSubscription() {
    setPortalLoading(true)
    setPortalError(null)
    try {
      const res = await fetch('/api/subscription/portal', { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.error?.message || 'Unable to open subscription management')
      }
      const body = await res.json()
      window.location.href = body.data.url
    } catch (err) {
      setPortalError(err instanceof Error ? err.message : 'Unable to open subscription management')
      setPortalLoading(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-5 w-[200px]" />
            <Skeleton className="h-5 w-[150px]" />
            <Skeleton className="h-5 w-[180px]" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2">
            <div>
              <dt className="text-muted-foreground text-sm">Email</dt>
              <dd className="text-sm font-medium">{userEmail}</dd>
            </div>
          </dl>
          <div className="mt-4 space-y-2">
            <p className="text-destructive text-sm">{error}</p>
            <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
              Try again
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!subscription) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2">
            <div>
              <dt className="text-muted-foreground text-sm">Email</dt>
              <dd className="text-sm font-medium">{userEmail}</dd>
            </div>
          </dl>
          <div className="mt-4 space-y-2">
            <p className="text-muted-foreground text-sm">No active subscription</p>
            <Link href="/pricing" className={buttonVariants()}>
              View plans
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  const config = STATUS_CONFIG[subscription.status]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subscription</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="space-y-2">
          <div>
            <dt className="text-muted-foreground text-sm">Email</dt>
            <dd className="text-sm font-medium">{userEmail}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-sm">Plan</dt>
            <dd className="text-sm font-medium">{getPlanLabel(subscription.plan)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-sm">Status</dt>
            <dd>
              {'className' in config ? (
                <Badge className={config.className}>{config.label}</Badge>
              ) : (
                <Badge variant={config.variant}>{config.label}</Badge>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-sm">{config.dateLabel}</dt>
            <dd className="text-sm font-medium">{formatDate(subscription.current_period_end)}</dd>
          </div>
        </dl>
        <div className="mt-4">
          <Button
            variant="outline"
            className="w-full sm:w-auto"
            disabled={portalLoading}
            onClick={handleManageSubscription}
          >
            {portalLoading ? 'Loading...' : 'Manage Subscription'}
          </Button>
          {portalError && <p className="text-destructive mt-2 text-sm">{portalError}</p>}
        </div>
      </CardContent>
    </Card>
  )
}
