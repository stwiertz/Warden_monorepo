// @vitest-environment node
//
// Story 4.1 (UX-DR16, FU-3) — A11Y-001 contrast guard for the web theme tokens.
// jsdom does not compute Tailwind styles, so the ratios are computed from the `:root`
// token values in globals.css with the WCAG 2.1 relative-luminance formula. Every pair
// below is a real surface; the recorded numbers live in
// _bmad-output/web-contrast-audit-2026-10-04.md.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(path.resolve(__dirname, 'globals.css'), 'utf8')

function rootTokens(source: string): Record<string, string> {
  const block = /:root\s*\{([\s\S]*?)\}/.exec(source)
  if (!block) throw new Error(':root block not found in globals.css')
  const tokens: Record<string, string> = {}
  for (const m of block[1].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) {
    tokens[m[1]] = m[2].trim().toLowerCase()
  }
  return tokens
}

const t = rootTokens(css)

function rgb(hex: string): [number, number, number] {
  const m = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!m) throw new Error(`not a #rrggbb colour: ${hex}`)
  const n = parseInt(m[1], 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** `top` at `alpha` composited over opaque `under` (e.g. Tailwind `bg-primary/10`). */
function over(top: string, alpha: number, under: string): string {
  const a = rgb(top)
  const u = rgb(under)
  return (
    '#' +
    a
      .map((c, i) =>
        Math.round(c * alpha + u[i] * (1 - alpha))
          .toString(16)
          .padStart(2, '0'),
      )
      .join('')
  )
}

const AA_TEXT = 4.5 // WCAG 1.4.3, normal-size text (CTA labels are 16px/600 — not "large")
const AA_NON_TEXT = 3 // WCAG 1.4.11, focus indicators + meaningful icons

describe('Story 4.1 — FU-3 token bump', () => {
  it('anchors the brand accent on #ff6b00 and accent-hover on #ff8533', () => {
    expect(t.primary).toBe('#ff6b00')
    expect(t['primary-hover']).toBe('#ff8533')
    expect(t.ring).toBe('#ff6b00')
    expect(t['chart-1']).toBe('#ff6b00')
    expect(t['chart-2']).toBe('#ff8533')
    expect(t['sidebar-primary']).toBe('#ff6b00')
    expect(t['sidebar-ring']).toBe('#ff6b00')
  })

  it('exposes accent-hover as a Tailwind colour (bg-primary-hover)', () => {
    expect(css).toMatch(/--color-primary-hover:\s*var\(--primary-hover\);/)
  })

  it('keeps shadcn --accent as the neutral hover surface (not the brand orange)', () => {
    expect(t.accent).toBe('#252525')
  })

  it('leaves no legacy #e8731a / #f28a2e value behind', () => {
    expect(css.toLowerCase()).not.toMatch(/#e8731a|#f28a2e/)
  })
})

describe('Story 4.1 — A11Y-001 contrast re-verify (WCAG AA)', () => {
  const textPairs: Array<[surface: string, fg: string, bg: string]> = [
    ['text-primary on page bg', t.foreground, t.background],
    ['text-primary on card', t['card-foreground'], t.card],
    ['text-secondary on page bg', t['muted-foreground'], t.background],
    ['text-secondary on card', t['muted-foreground'], t.card],
    ['orange text on page bg (links, savings label)', t.primary, t.background],
    ['orange text on card (AuthFormToggle links, PlanCard savings)', t.primary, t.card],
    [
      'button-default label on orange fill (CTA, featured badge)',
      t['primary-foreground'],
      t.primary,
    ],
    ['button-hover label on accent-hover fill', t['primary-foreground'], t['primary-hover']],
    ['skip-link label on orange (focus)', t['primary-foreground'], t.primary],
  ]

  it.each(textPairs)('%s meets 4.5:1', (_surface, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(AA_TEXT)
  })

  it('matches the PRD A11Y-001 headline figures (text-primary ~16:1, text-secondary ~5.5:1, orange ~4.8:1)', () => {
    expect(contrast(t.foreground, t.background)).toBeGreaterThanOrEqual(15)
    expect(contrast(t['muted-foreground'], t.background)).toBeGreaterThanOrEqual(5.5)
    expect(contrast(t.primary, t.background)).toBeGreaterThanOrEqual(4.8)
  })

  const nonTextPairs: Array<[surface: string, fg: string, bg: string]> = [
    ['focus ring on page bg', t.ring, t.background],
    ['focus ring on card', t.ring, t.card],
    ['landing feature icon on bg-primary/10 tile', t.primary, over(t.primary, 0.1, t.background)],
    [
      'landing feature icon on bg-primary/10 tile inside bg-card',
      t.primary,
      over(t.primary, 0.1, t.card),
    ],
    ['featured PlanCard border on page bg', t.primary, t.background],
  ]

  it.each(nonTextPairs)('%s meets 3:1', (_surface, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(AA_NON_TEXT)
  })

  it('draws the base focus outline with the opaque ring (outline-ring/50 is ~2.4:1 and fails 3:1)', () => {
    expect(css).toMatch(/@apply border-border outline-ring;/)
    expect(contrast(over(t.ring, 0.5, t.background), t.background)).toBeLessThan(AA_NON_TEXT)
  })

  it('documents why the on-accent foreground is dark: white on #ff6b00 fails AA', () => {
    expect(contrast('#ffffff', t.primary)).toBeLessThan(AA_TEXT)
    expect(t['primary-foreground']).toBe(t.background)
  })
})
