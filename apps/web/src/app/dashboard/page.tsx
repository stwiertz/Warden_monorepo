'use client'

import { useSearchParams } from 'next/navigation'

import { useAuth } from '@/hooks/useAuth'
import { useSubscription } from '@/hooks/useSubscription'
import { SignOutButton } from '@/components/auth/SignOutButton'
import { SubscriptionCard } from '@/components/dashboard/SubscriptionCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardPage() {
  const { user, loading } = useAuth()
  const { subscription, loading: subscriptionLoading, error: subscriptionError } = useSubscription()
  const searchParams = useSearchParams()
  const showCheckoutSuccess = searchParams?.get('checkout') === 'success'

  if (loading || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-5 w-64" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col items-center px-4 py-12">
      <div className="w-full max-w-md space-y-4">
        {showCheckoutSuccess && (
          <Alert data-testid="checkout-success-banner" role="status" aria-live="polite">
            <AlertTitle>Subscription started — welcome to Warden!</AlertTitle>
            <AlertDescription>It may take a few seconds for your plan to appear.</AlertDescription>
          </Alert>
        )}
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <SubscriptionCard
          subscription={subscription}
          loading={subscriptionLoading}
          error={subscriptionError}
          userEmail={user.email}
        />
        <SignOutButton variant="outline" />
      </div>
    </div>
  )
}
