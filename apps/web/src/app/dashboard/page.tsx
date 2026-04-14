'use client'

import { useSearchParams } from 'next/navigation'

import { useAuth } from '@/hooks/useAuth'
import { SignOutButton } from '@/components/auth/SignOutButton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardPage() {
  const { user, loading } = useAuth()
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
        <div className="space-y-1">
          <p className="text-muted-foreground text-sm">
            Signed in as <span className="text-foreground font-medium">{user.displayName}</span>
          </p>
          <p className="text-muted-foreground text-sm">{user.email}</p>
        </div>
        <SignOutButton variant="outline" />
      </div>
    </div>
  )
}
