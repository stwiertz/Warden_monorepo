import { describe, expect, it } from 'vitest'

import { defaultTwitter, LANDING_OG_IMAGE, OG_COPY } from './og'
import { rootMetadata } from './root-metadata'

describe('rootMetadata', () => {
  // The production loopback guard is covered in site-url.test.ts.
  it('sets an absolute, path-free metadataBase', () => {
    const base = rootMetadata.metadataBase
    expect(base).toBeInstanceOf(URL)
    expect((base as URL).protocol).toMatch(/^https?:$/)
    expect((base as URL).pathname).toBe('/')
  })

  it('keeps the title template and uses the epic AC default title', () => {
    expect(rootMetadata.title).toEqual({
      default: 'Warden — Coaching companion mobile pour joueurs compétitifs',
      template: '%s | Warden',
    })
    expect(rootMetadata.description).toBe(OG_COPY.landingDescription)
  })

  it('carries the landing OG card with the 1200×630 image', () => {
    expect(rootMetadata.openGraph).toMatchObject({
      type: 'website',
      url: '/',
      title: OG_COPY.landingTitle,
      locale: 'fr_FR',
      siteName: 'Warden',
      images: [LANDING_OG_IMAGE],
    })
  })

  it('carries the summary_large_image Twitter card', () => {
    expect(rootMetadata.twitter).toEqual(defaultTwitter)
  })
})
