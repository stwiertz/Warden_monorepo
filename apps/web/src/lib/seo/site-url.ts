/** Canonical public origin (UX §3.3.1). Used when NEXT_PUBLIC_APP_URL is unset or unusable. */
export const DEFAULT_SITE_URL = 'https://warden.team'

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '0.0.0.0'])

/**
 * Absolute site origin for `metadataBase`. Without it Next resolves relative OG image URLs
 * against VERCEL_* env vars or `http://localhost:3000` — this app is on Firebase, so production
 * would ship a localhost `og:image` and Discord would render a blank card.
 *
 * NEXT_PUBLIC_* is inlined at build time: the production build must set it to the public origin.
 * A loopback value (`.env.example` ships `http://localhost:3000`) is ignored in production builds,
 * so a leaked dev value falls back to the canonical origin instead of shipping localhost URLs.
 */
export function resolveSiteUrl(
  value: string | undefined = process.env.NEXT_PUBLIC_APP_URL,
  production: boolean = process.env.NODE_ENV === 'production',
): URL {
  const trimmed = value?.trim()
  if (trimmed) {
    try {
      const url = new URL(trimmed)
      const usable = url.protocol === 'https:' || url.protocol === 'http:'
      if (usable && !(production && LOOPBACK_HOSTS.has(url.hostname))) {
        return new URL(url.origin)
      }
    } catch {
      // not an absolute URL — fall through to the canonical origin
    }
  }
  return new URL(DEFAULT_SITE_URL)
}
