'use client'

import { useState } from 'react'

import { GoogleSignInButton } from '@/components/auth/GoogleSignInButton'
import { EmailSignInForm } from '@/components/auth/EmailSignInForm'
import { RegistrationForm } from '@/components/auth/RegistrationForm'

export function AuthFormToggle() {
  const [mode, setMode] = useState<'sign-in' | 'register'>('sign-in')

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold tracking-tight">
          {mode === 'sign-in' ? 'Sign in to Warden' : 'Create your account'}
        </h1>
        <p className="text-muted-foreground text-sm">
          {mode === 'sign-in'
            ? 'Sign in to your Warden account'
            : 'Get started with a free account'}
        </p>
      </div>

      <GoogleSignInButton />

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background text-muted-foreground px-2">or</span>
        </div>
      </div>

      {mode === 'sign-in' ? <EmailSignInForm /> : <RegistrationForm />}

      <p className="text-muted-foreground text-center text-sm">
        {mode === 'sign-in' ? (
          <>
            Don&apos;t have an account?{' '}
            <button
              type="button"
              onClick={() => setMode('register')}
              className="text-primary underline-offset-4 hover:underline"
            >
              Create one
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button
              type="button"
              onClick={() => setMode('sign-in')}
              className="text-primary underline-offset-4 hover:underline"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  )
}
