import type { Metadata } from 'next'

type OpenGraph = NonNullable<Metadata['openGraph']>
type Twitter = NonNullable<Metadata['twitter']>

export type OgImage = {
  url: string
  width: number
  height: number
  type: string
  alt: string
}

/** At least one image: an empty list would ship a card with no `og:image`. */
export type OgImages = [OgImage, ...OgImage[]]

/**
 * Open Graph / Twitter copy — UX §4.2.9, verbatim. French on purpose even though the web UI is
 * English: the previews are consumed in FR/BE Discord channels (I18N-002).
 */
export const OG_COPY = {
  landingTitle: 'Warden — Le clip est le produit. Le téléphone suffit.',
  landingDescription:
    "L'app de coaching mobile pour joueurs FPS compétitifs. Auto-slicing, minimap, voix, partage Discord — tout sur le téléphone.",
  pricingTitle: 'Warden — €7.99/mois ou €79.90/an. Coaching FPS sur mobile.',
  twitterTitle: 'Warden — Progresser plus vite en investissant moins de temps.',
  twitterDescription: "L'app de coaching mobile pour joueurs FPS compétitifs.",
} as const

/** Static asset produced by `scripts/og/generate-landing-og.mjs` (UX §3.3.2). */
export const LANDING_OG_IMAGE: OgImage = {
  url: '/og/landing.jpg',
  width: 1200,
  height: 630,
  type: 'image/jpeg',
  alt: 'Warden — Progresser plus vite en investissant moins de temps.',
}

/**
 * A route's `openGraph` block. Next merges metadata shallowly, so a route that sets `openGraph`
 * replaces the root one wholesale — building it here guarantees the image is never dropped.
 */
export function buildOpenGraph({
  path,
  title = OG_COPY.landingTitle,
  description = OG_COPY.landingDescription,
  images = [LANDING_OG_IMAGE],
}: {
  path: string
  title?: string
  description?: string
  images?: OgImages
}): OpenGraph {
  return {
    type: 'website',
    url: path,
    title,
    description,
    siteName: 'Warden',
    locale: 'fr_FR',
    images,
  }
}

export const defaultTwitter: Twitter = {
  card: 'summary_large_image',
  title: OG_COPY.twitterTitle,
  description: OG_COPY.twitterDescription,
  images: [LANDING_OG_IMAGE.url],
}
