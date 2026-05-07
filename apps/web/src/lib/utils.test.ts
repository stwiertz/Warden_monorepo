import { describe, it, expect } from 'vitest'

import { sanitizeRedirect } from './utils'

describe('sanitizeRedirect', () => {
  it('returns /dashboard when next is null', () => {
    expect(sanitizeRedirect(null)).toBe('/dashboard')
  })

  it('returns /dashboard when next is undefined', () => {
    expect(sanitizeRedirect(undefined)).toBe('/dashboard')
  })

  it('returns /dashboard when next is empty string', () => {
    expect(sanitizeRedirect('')).toBe('/dashboard')
  })

  it('returns /dashboard for safe path /dashboard', () => {
    expect(sanitizeRedirect('/dashboard')).toBe('/dashboard')
  })

  it('preserves nested path with query string', () => {
    expect(sanitizeRedirect('/dashboard/settings?x=1')).toBe('/dashboard/settings?x=1')
  })

  it('rejects protocol-relative //evil.com', () => {
    expect(sanitizeRedirect('//evil.com')).toBe('/dashboard')
  })

  it('rejects backslash trick /\\evil.com', () => {
    expect(sanitizeRedirect('/\\evil.com')).toBe('/dashboard')
  })

  it('rejects full URL https://evil.com', () => {
    expect(sanitizeRedirect('https://evil.com')).toBe('/dashboard')
  })

  it('rejects relative paths without leading slash', () => {
    expect(sanitizeRedirect('dashboard')).toBe('/dashboard')
  })
})
