import { describe, expect, it } from 'vitest'

import { DEFAULT_SITE_URL, resolveSiteUrl } from './site-url'

describe('resolveSiteUrl', () => {
  it('uses the env value when it is an absolute https URL', () => {
    expect(resolveSiteUrl('https://staging.warden.team').href).toBe('https://staging.warden.team/')
  })

  it('accepts http localhost outside production (local dev)', () => {
    expect(resolveSiteUrl('http://localhost:3000', false).href).toBe('http://localhost:3000/')
  })

  it.each(['http://localhost:3000', 'http://127.0.0.1:3000', 'http://[::1]:3000'])(
    'ignores the loopback value %j in a production build',
    (value) => {
      expect(resolveSiteUrl(value, true).href).toBe(`${DEFAULT_SITE_URL}/`)
    },
  )

  it('keeps a real origin in a production build', () => {
    expect(resolveSiteUrl('https://staging.warden.team', true).href).toBe(
      'https://staging.warden.team/',
    )
  })

  it('reduces the value to its origin (no basePath, so a path would 404 the image)', () => {
    expect(resolveSiteUrl('https://warden.team/app/').href).toBe('https://warden.team/')
  })

  it('normalises a trailing slash', () => {
    expect(resolveSiteUrl('https://warden.team/').href).toBe('https://warden.team/')
  })

  it.each([undefined, '', '   ', 'warden.team', '/relative', 'not a url', 'ftp://warden.team'])(
    'falls back to the canonical origin for %j',
    (value) => {
      expect(resolveSiteUrl(value).href).toBe(`${DEFAULT_SITE_URL}/`)
    },
  )

  it('canonical fallback is warden.team (UX §3.3.1)', () => {
    expect(DEFAULT_SITE_URL).toBe('https://warden.team')
  })
})
