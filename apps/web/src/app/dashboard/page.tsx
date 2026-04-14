'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

import { useAuth } from '@/hooks/useAuth'
import { SignOutButton } from '@/components/auth/SignOutButton'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardPage() {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/auth/sign-in')
    }
  }, [loading, user, router])

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
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-4">
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
