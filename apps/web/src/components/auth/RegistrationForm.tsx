'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createUserWithEmailAndPassword } from 'firebase/auth'

import { auth } from '@/lib/firebase/client'
import { getRegistrationErrorMessage } from '@/lib/firebase/errors'
import { createSessionAndRedirect } from '@/lib/firebase/session'
import { registrationSchema } from '@/lib/schemas/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import type { RegistrationFormData } from '@/lib/schemas/auth'

export function RegistrationForm() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [firebaseError, setFirebaseError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<RegistrationFormData>({
    resolver: zodResolver(registrationSchema),
  })

  async function onSubmit(data: RegistrationFormData) {
    setIsLoading(true)
    setFirebaseError(null)

    try {
      const result = await createUserWithEmailAndPassword(auth, data.email, data.password)
      await createSessionAndRedirect(result.user, router.push)
    } catch (err) {
      setFirebaseError(getRegistrationErrorMessage(err))
      setValue('password', '')
      setValue('confirmPassword', '')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <label htmlFor="reg-email" className="text-sm font-medium">
          Email
        </label>
        <Input
          id="reg-email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'reg-email-error' : undefined}
          {...register('email')}
        />
        {errors.email && (
          <p id="reg-email-error" className="text-destructive text-sm" role="alert">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="reg-password" className="text-sm font-medium">
          Password
        </label>
        <Input
          id="reg-password"
          type="password"
          placeholder="At least 8 characters"
          autoComplete="new-password"
          aria-invalid={!!errors.password}
          aria-describedby={errors.password ? 'reg-password-error' : undefined}
          {...register('password')}
        />
        {errors.password && (
          <p id="reg-password-error" className="text-destructive text-sm" role="alert">
            {errors.password.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="reg-confirm-password" className="text-sm font-medium">
          Confirm Password
        </label>
        <Input
          id="reg-confirm-password"
          type="password"
          placeholder="Confirm your password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirmPassword}
          aria-describedby={errors.confirmPassword ? 'reg-confirm-password-error' : undefined}
          {...register('confirmPassword')}
        />
        {errors.confirmPassword && (
          <p id="reg-confirm-password-error" className="text-destructive text-sm" role="alert">
            {errors.confirmPassword.message}
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
            Creating account...
          </>
        ) : (
          'Create account'
        )}
      </Button>
    </form>
  )
}
