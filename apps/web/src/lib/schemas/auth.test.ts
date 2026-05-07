import { describe, it, expect } from 'vitest'
import { signInSchema, registrationSchema } from './auth'

describe('signInSchema', () => {
  it('validates a correct sign-in input', () => {
    const result = signInSchema.safeParse({ email: 'user@example.com', password: 'mypassword' })
    expect(result.success).toBe(true)
  })

  it('rejects invalid email', () => {
    const result = signInSchema.safeParse({ email: 'notanemail', password: 'mypassword' })
    expect(result.success).toBe(false)
  })

  it('rejects empty email', () => {
    const result = signInSchema.safeParse({ email: '', password: 'mypassword' })
    expect(result.success).toBe(false)
  })

  it('rejects empty password', () => {
    const result = signInSchema.safeParse({ email: 'user@example.com', password: '' })
    expect(result.success).toBe(false)
  })

  it('accepts password of any length (min 1)', () => {
    const result = signInSchema.safeParse({ email: 'user@example.com', password: 'x' })
    expect(result.success).toBe(true)
  })
})

describe('registrationSchema', () => {
  it('validates a correct registration input', () => {
    const result = registrationSchema.safeParse({
      email: 'user@example.com',
      password: '12345678',
      confirmPassword: '12345678',
    })
    expect(result.success).toBe(true)
  })

  it('rejects invalid email', () => {
    const result = registrationSchema.safeParse({
      email: 'notanemail',
      password: '12345678',
      confirmPassword: '12345678',
    })
    expect(result.success).toBe(false)
  })

  it('rejects password shorter than 8 characters', () => {
    const result = registrationSchema.safeParse({
      email: 'user@example.com',
      password: '1234567',
      confirmPassword: '1234567',
    })
    expect(result.success).toBe(false)
  })

  it('rejects mismatched passwords', () => {
    const result = registrationSchema.safeParse({
      email: 'user@example.com',
      password: '12345678',
      confirmPassword: '87654321',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const confirmError = result.error.issues.find((i) => i.path?.includes('confirmPassword'))
      expect(confirmError?.message).toBe('Passwords do not match')
    }
  })

  it('accepts exactly 8 character password', () => {
    const result = registrationSchema.safeParse({
      email: 'user@example.com',
      password: 'abcdefgh',
      confirmPassword: 'abcdefgh',
    })
    expect(result.success).toBe(true)
  })
})
