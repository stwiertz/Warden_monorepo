import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { LANDING_OG_IMAGE } from '@/lib/seo/og'

// The asset the metadata points at (UX §3.3.2): 1200×630 JPEG, sRGB, ≤ 200 KB.
const file = path.resolve(__dirname, '../../public', LANDING_OG_IMAGE.url.replace(/^\//, ''))
const bytes = readFileSync(file)

type Segment = { marker: number; payload: Buffer }

/** Walks the JPEG marker segments up to the start of scan. */
function segments(buf: Buffer): Segment[] {
  const out: Segment[] = []
  let i = 2
  while (i + 4 <= buf.length && buf[i] === 0xff) {
    const marker = buf[i + 1]
    if (marker === 0xda) break // SOS — entropy-coded data follows
    const len = buf.readUInt16BE(i + 2)
    out.push({ marker, payload: buf.subarray(i + 4, i + 2 + len) })
    i += 2 + len
  }
  return out
}

// SOF0–SOF15, minus DHT (C4), JPG (C8) and DAC (CC).
const isFrameHeader = (m: number) => m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)

describe('public/og/landing.jpg', () => {
  const segs = segments(bytes)

  it('is a JPEG', () => {
    expect(bytes.subarray(0, 2)).toEqual(Buffer.from([0xff, 0xd8]))
    expect(bytes.subarray(-2)).toEqual(Buffer.from([0xff, 0xd9]))
  })

  it('is 1200×630, matching the og:image width/height metadata', () => {
    const sof = segs.find((s) => isFrameHeader(s.marker))
    expect(sof).toBeDefined()
    const height = sof!.payload.readUInt16BE(1)
    const width = sof!.payload.readUInt16BE(3)
    expect([width, height]).toEqual([LANDING_OG_IMAGE.width, LANDING_OG_IMAGE.height])
  })

  it('stays under the 200 KB budget', () => {
    expect(bytes.length).toBeLessThanOrEqual(200 * 1024)
  })

  it('embeds an sRGB ICC profile', () => {
    const icc = segs.filter(
      (s) => s.marker === 0xe2 && s.payload.subarray(0, 12).toString('latin1') === 'ICC_PROFILE\0',
    )
    expect(icc.length).toBeGreaterThan(0)
    const profile = Buffer.concat(icc.map((s) => s.payload.subarray(14)))
    expect(profile.subarray(16, 20).toString('latin1')).toBe('RGB ') // colour space
    // The description tag is either ASCII (`desc`) or UTF-16BE (`mluc`).
    const utf16be = Buffer.from('sRGB', 'utf16le').swap16()
    expect(profile.includes('sRGB', 0, 'latin1') || profile.includes(utf16be)).toBe(true)
  })
})
