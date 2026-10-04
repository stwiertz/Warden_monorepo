import type { Metadata } from 'next'

import { buildOpenGraph, defaultTwitter, OG_COPY } from './og'
import { resolveSiteUrl } from './site-url'

/** Root-layout metadata. Lives outside layout.tsx so it can be tested without `next/font`. */
export const rootMetadata: Metadata = {
  metadataBase: resolveSiteUrl(),
  title: {
    default: 'Warden — Coaching companion mobile pour joueurs compétitifs',
    template: '%s | Warden',
  },
  description: OG_COPY.landingDescription,
  openGraph: buildOpenGraph({ path: '/' }),
  twitter: defaultTwitter,
}
