#!/usr/bin/env node
/**
 * Generates public/og/landing.jpg — the 1200×630 Open Graph card (UX §3.3.2, Story 4.2).
 *
 *   node scripts/og/generate-landing-og.mjs --font <Inter variable .ttf> [--out <path>]
 *
 * Static asset, not a runtime route: UX §3.3.2 asks for an exported file. Re-run this when the
 * tagline, the accent (FU-3) or the composition changes, then commit the JPEG.
 *
 * sharp is Next's own optional dependency, resolved from Next's install location, so apps/web
 * gains no dependency. Text is rendered by Pango, whose FreeType build does NOT read WOFF2 (it
 * silently falls back to another face), so the vendored src/fonts/*.woff2 must be decompressed
 * to TTF first, e.g. with fontTools (`pip install fonttools brotli`):
 *
 *   python -c "from fontTools.ttLib import TTFont as F; f=F('src/fonts/inter-latin-wght-normal.woff2'); f.flavor=None; f.save('inter.ttf')"
 *
 * or use InterVariable.ttf from https://github.com/rsms/inter/releases (OFL-1.1).
 */
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'

const require = createRequire(import.meta.url)
const sharp = createRequire(require.resolve('next/package.json'))('sharp')

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const { values } = parseArgs({
  options: {
    font: { type: 'string' },
    out: { type: 'string', default: path.join(webRoot, 'public/og/landing.jpg') },
  },
})
if (!values.font || !existsSync(values.font) || !/\.(ttf|otf)$/i.test(values.font)) {
  console.error('--font <Inter variable .ttf|.otf> is required (WOFF2 is not readable by Pango)')
  process.exit(1)
}

const W = 1200
const H = 630
const MARGIN = 72
const MAX_BYTES = 200 * 1024

// Theme tokens (src/app/globals.css :root, after Story 4.1).
const C = {
  bg: '#0F0F0F',
  fg: '#F0F0F0',
  muted: '#999999',
  accent: '#FF6B00',
  onAccent: '#0F0F0F',
}

// FR-locked hero (I18N-002) — verbatim; the line break is layout only.
const HERO = ['Progresser plus vite', 'en investissant moins de temps.']
const SUBTITLE = 'Coaching FPS sur mobile · Auto-slicing · Voix · Discord-ready'
const URL_CHIP = 'warden.team'

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** Renders one text block to a transparent PNG; returns { input, width, height }. */
async function text(content, { size, weight, color, spacing = 0 }) {
  const markup = `<span foreground="${color}" weight="${weight}">${content}</span>`
  const { data, info } = await sharp({
    text: {
      text: markup,
      font: `Inter ${size}`,
      fontfile: values.font,
      rgba: true,
      dpi: 72, // 1pt = 1px
      spacing,
    },
  })
    .png()
    .toBuffer({ resolveWithObject: true })
  return { input: data, width: info.width, height: info.height }
}

const svg = (body) =>
  Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">${body}</svg>`)

// Brand row: "W" mark + wordmark.
const MARK = 64
const markTop = 64
const markLetter = await text('W', { size: 40, weight: 800, color: C.onAccent })
const wordmark = await text('WARDEN', { size: 32, weight: 700, color: C.fg })

// Hero, subtitle, URL chip.
const hero = await text(HERO.map(escape).join('\n'), {
  size: 64,
  weight: 800,
  color: C.fg,
  spacing: 8,
})
const subtitle = await text(escape(SUBTITLE), { size: 26, weight: 400, color: C.muted })
const chipText = await text(URL_CHIP, { size: 24, weight: 600, color: C.fg })
const CHIP_PAD_X = 22
const CHIP_H = 52
const chipW = chipText.width + CHIP_PAD_X * 2
const chipLeft = W - MARGIN - chipW
const chipTop = H - 64 - CHIP_H

const heroTop = 212
const subtitleTop = heroTop + hero.height + 36

const shapes = svg(`
  <rect x="0" y="0" width="${W}" height="${H}" fill="${C.bg}"/>
  <rect x="5" y="5" width="${W - 10}" height="${H - 10}" fill="none" stroke="${C.accent}" stroke-width="10"/>
  <rect x="${MARGIN}" y="${markTop}" width="${MARK}" height="${MARK}" rx="12" fill="${C.accent}"/>
  <rect x="${chipLeft}" y="${chipTop}" width="${chipW}" height="${CHIP_H}" rx="10" fill="none" stroke="${C.accent}" stroke-width="2"/>
`)

const out = path.resolve(values.out)

const jpeg = await sharp(shapes)
  .composite([
    {
      input: markLetter.input,
      left: MARGIN + Math.round((MARK - markLetter.width) / 2),
      top: markTop + Math.round((MARK - markLetter.height) / 2),
    },
    {
      input: wordmark.input,
      left: MARGIN + MARK + 20,
      top: markTop + Math.round((MARK - wordmark.height) / 2),
    },
    { input: hero.input, left: MARGIN, top: heroTop },
    { input: subtitle.input, left: MARGIN, top: subtitleTop },
    {
      input: chipText.input,
      left: chipLeft + CHIP_PAD_X,
      top: chipTop + Math.round((CHIP_H - chipText.height) / 2),
    },
  ])
  .toColourspace('srgb')
  .withIccProfile('srgb')
  .jpeg({ quality: 90, mozjpeg: true, chromaSubsampling: '4:4:4' })
  .toBuffer()

// Check the budget before writing, so a failed run never replaces the committed asset.
const kb = `${(jpeg.length / 1024).toFixed(1)} KB`
if (jpeg.length > MAX_BYTES) {
  console.error(`${W}×${H}, ${kb}: over the 200 KB budget (UX §3.3.2), ${out} left untouched`)
  process.exit(1)
}
mkdirSync(path.dirname(out), { recursive: true })
writeFileSync(out, jpeg)
console.log(`${path.relative(process.cwd(), out)}: ${W}×${H}, ${kb}`)
