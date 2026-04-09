'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { signOut } from 'firebase/auth'

import { auth } from '@/lib/firebase/client'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [isSigningOut, setIsSigningOut] = useState(false)

  async function handleSignOut() {
    setIsSigningOut(true)
    try {
      await signOut(auth)
      await fetch('/api/auth/session', { method: 'DELETE' })
      router.push('/')
    } catch {
      setIsSigningOut(false)
    }
  }

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
        <Button variant="outline" onClick={handleSignOut} disabled={isSigningOut}>
          {isSigningOut ? 'Signing out...' : 'Sign out'}
        </Button>
      </div>
    </div>
  )
}
