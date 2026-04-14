'use client'

import { useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { signInWithEmailAndPassword } from 'firebase/auth'

import { auth } from '@/lib/firebase/client'
import { getSignInErrorMessage } from '@/lib/firebase/errors'
import { createSessionAndRedirect } from '@/lib/firebase/session'
import { signInSchema } from '@/lib/schemas/auth'
import { sanitizeRedirect } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import type { SignInFormData } from '@/lib/schemas/auth'

export function EmailSignInForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextTarget = sanitizeRedirect(searchParams.get('next'))
  const [isLoading, setIsLoading] = useState(false)
  const [firebaseError, setFirebaseError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<SignInFormData>({
    resolver: zodResolver(signInSchema),
  })

  async function onSubmit(data: SignInFormData) {
    setIsLoading(true)
    setFirebaseError(null)

    try {
      const result = await signInWithEmailAndPassword(auth, data.email, data.password)
      await createSessionAndRedirect(result.user, () => router.push(nextTarget))
    } catch (err) {
      setFirebaseError(getSignInErrorMessage(err))
      setValue('password', '')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <label htmlFor="email" className="text-sm font-medium">
          Email
        </label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'email-error' : undefined}
          {...register('email')}
        />
        {errors.email && (
          <p id="email-error" className="text-destructive text-sm" role="alert">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="password" className="text-sm font-medium">
          Password
        </label>
        <Input
          id="password"
          type="password"
          placeholder="Enter your password"
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          aria-describedby={errors.password ? 'password-error' : undefined}
          {...register('password')}
        />
        {errors.password && (
          <p id="password-error" className="text-destructive text-sm" role="alert">
            {errors.password.message}
          </p>
        )}
      </div>

      {firebaseError && (
        <p className="text-destructive text-center text-sm" role="alert">
          {firebaseError}
        </p>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={isLoading}>
        {isLoading ? (
          <>
            <span className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Signing in...
          </>
        ) : (
          'Sign in'
        )}
      </Button>
    </form>
  )
}
