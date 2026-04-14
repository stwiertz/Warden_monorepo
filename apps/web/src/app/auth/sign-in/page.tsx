import { AuthFormToggle } from '@/components/auth/AuthFormToggle'

import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign In',
}

export default function SignInPage() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <AuthFormToggle />
      </div>
    </div>
  )
}
