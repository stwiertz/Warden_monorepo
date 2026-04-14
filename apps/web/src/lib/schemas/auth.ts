import { z } from 'zod/v4'

export const signInSchema = z.object({
  email: z.email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

export const registrationSchema = z
  .object({
    email: z.email('Please enter a valid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .check((ctx) => {
    if (ctx.value.password !== ctx.value.confirmPassword) {
      ctx.issues.push({
        code: 'custom',
        input: ctx.value.confirmPassword,
        message: 'Passwords do not match',
        path: ['confirmPassword'],
      })
    }
  })

export type SignInFormData = z.infer<typeof signInSchema>
export type RegistrationFormData = z.infer<typeof registrationSchema>
