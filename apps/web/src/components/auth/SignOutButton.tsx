'use client'

import { useState, type ComponentProps, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@/components/ui/button'

type ButtonProps = ComponentProps<typeof Button>

type SignOutButtonProps = {
  variant?: ButtonProps['variant']
  size?: ButtonProps['size']
  className?: string
  children?: ReactNode
}

export function SignOutButton({ variant, size, className, children }: SignOutButtonProps) {
  const router = useRouter()
  const [isSigningOut, setIsSigningOut] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSignOut() {
    setIsSigningOut(true)
    setError(null)
    try {
      // Dynamic import keeps firebase/auth out of the Header's bundle on anonymous pages.
      const { destroySessionAndRedirect } = await import('@/lib/firebase/session')
      await destroySessionAndRedirect(router.push)
      router.refresh()
    } catch {
      setError('Unable to sign out. Please try again.')
      setIsSigningOut(false)
    }
  }

  return (
    <div className="relative inline-flex flex-col">
      <Button
        variant={variant}
        size={size}
        className={className}
        onClick={handleSignOut}
        disabled={isSigningOut}
      >
        {isSigningOut ? (
          <span className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : null}
        <span className={isSigningOut ? 'ml-2' : undefined}>
          {isSigningOut ? 'Signing out...' : (children ?? 'Sign out')}
        </span>
      </Button>
      {error && (
        <p
          className="text-destructive bg-background absolute top-full left-0 mt-1 rounded-md border px-2 py-1 text-xs whitespace-nowrap shadow-sm"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  )
}
