import { describe, expect, it } from 'vitest'

import { buildOpenGraph, defaultTwitter, LANDING_OG_IMAGE, OG_COPY } from './og'

describe('OG copy (UX §4.2.9, verbatim)', () => {
  it('keeps the FR strings character-for-character', () => {
    expect(OG_COPY.landingTitle).toBe('Warden — Le clip est le produit. Le téléphone suffit.')
    expect(OG_COPY.landingDescription).toBe(
      "L'app de coaching mobile pour joueurs FPS compétitifs. Auto-slicing, minimap, voix, partage Discord — tout sur le téléphone.",
    )
    expect(OG_COPY.pricingTitle).toBe('Warden — €7.99/mois ou €79.90/an. Coaching FPS sur mobile.')
    expect(OG_COPY.twitterTitle).toBe(
      'Warden — Progresser plus vite en investissant moins de temps.',
    )
    expect(OG_COPY.twitterDescription).toBe(
      "L'app de coaching mobile pour joueurs FPS compétitifs.",
    )
  })
})

describe('LANDING_OG_IMAGE', () => {
  it('points at the static 1200×630 JPEG', () => {
    expect(LANDING_OG_IMAGE).toMatchObject({
      url: '/og/landing.jpg',
      width: 1200,
      height: 630,
      type: 'image/jpeg',
    })
    expect(LANDING_OG_IMAGE.alt.length).toBeGreaterThan(0)
  })
})

describe('buildOpenGraph', () => {
  it('defaults to the landing card', () => {
    expect(buildOpenGraph({ path: '/' })).toEqual({
      type: 'website',
      url: '/',
      title: OG_COPY.landingTitle,
      description: OG_COPY.landingDescription,
      siteName: 'Warden',
      locale: 'fr_FR',
      images: [LANDING_OG_IMAGE],
    })
  })

  it('always carries an image, so a route override cannot drop it (shallow merge)', () => {
    expect(buildOpenGraph({ path: '/pricing', title: 'x' }).images).toEqual([LANDING_OG_IMAGE])
  })

  it('lets a route override path, title, description and image', () => {
    const image = { url: '/og/pricing.jpg', width: 1200, height: 630, type: 'image/jpeg', alt: 'p' }
    expect(
      buildOpenGraph({ path: '/pricing', title: 't', description: 'd', images: [image] }),
    ).toMatchObject({ url: '/pricing', title: 't', description: 'd', images: [image] })
  })
})

describe('defaultTwitter', () => {
  it('is a large-image card with the twitter copy and the landing image', () => {
    expect(defaultTwitter).toEqual({
      card: 'summary_large_image',
      title: OG_COPY.twitterTitle,
      description: OG_COPY.twitterDescription,
      images: [LANDING_OG_IMAGE.url],
    })
  })
})
