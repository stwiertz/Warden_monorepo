'use client'

import Link from 'next/link'

import { useAuth } from '@/hooks/useAuth'
import { SignOutButton } from '@/components/auth/SignOutButton'

const linkClassName =
  'text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-3'

export function HeaderAuthActions() {
  const { user, loading } = useAuth()

  if (loading) {
    return <li aria-hidden="true" className="h-9 w-16" />
  }

  if (!user) {
    return (
      <>
        <li>
          <Link href="/" className={linkClassName}>
            Home
          </Link>
        </li>
        <li>
          <Link href="/pricing" className={linkClassName}>
            Pricing
          </Link>
        </li>
        <li>
          <Link href="/auth/sign-in" className={linkClassName}>
            Sign in
          </Link>
        </li>
      </>
    )
  }

  return (
    <>
      <li>
        <Link href="/" className={linkClassName}>
          Home
        </Link>
      </li>
      <li>
        <Link href="/dashboard" className={linkClassName}>
          Dashboard
        </Link>
      </li>
      <li>
        <SignOutButton variant="ghost" size="sm">
          Sign out
        </SignOutButton>
      </li>
    </>
  )
}
