import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton'

import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign In',
}

export default function SignInPage() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
          <p className="text-muted-foreground text-sm">Sign in to your Warden account</p>
        </div>
        <GoogleSignInButton />
      </div>
    </div>
  )
}
