// Reads contracts/*.schema.json and emits zod modules into src/generated/.
// Runs as part of `pnpm --filter @warden/contracts build`.
//
// Why: the schemas in contracts/ are the cross-language source of truth (Python tooling
// validates emitted JSON against them, TS apps need typed runtime parsers). Re-generating
// from JSON Schema keeps both sides locked to the same shape.

// 🔴 Story 12.4c — `$defs`/`$ref` ARE RESOLVED BEFORE CONVERSION, and that is the
// difference between a typed parser and a decorative one. `json-schema-to-zod`
// does not follow `$ref`: it emits `z.any()` for every referenced subschema. For
// `map-config.schema.json` that meant `hud_version_detection` and
// `in_match_detection` were `z.array(z.any())`, `roi` was `z.any()` and every map
// entry was `z.any()` — i.e. zero validation on exactly the zone fields the
// mobile engine consumes (zone rects, HSV bands, weights). Mobile got
// `MapConfigSchema` from `@warden/contracts` and "validated" nothing.
//
// Inlining is done here rather than in each consumer so the single source of
// truth stays `contracts/*.schema.json`, and so the Python side (which uses
// `jsonschema`, and does follow `$ref`) and the TS side keep agreeing.

import { jsonSchemaToZod } from 'json-schema-to-zod'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Inline every local `$ref` (`#/$defs/Name`) and drop the `$defs` block.
 *
 * Local refs only, and cycles are refused rather than expanded: a recursive
 * schema would inline forever, and silently producing a truncated type is worse
 * than failing the build. Neither shipped schema is recursive.
 */
function inlineLocalRefs(schema, root = schema, seen = []) {
  if (Array.isArray(schema)) return schema.map((s) => inlineLocalRefs(s, root, seen))
  if (schema === null || typeof schema !== 'object') return schema

  if (typeof schema.$ref === 'string') {
    const ref = schema.$ref
    if (!ref.startsWith('#/')) {
      throw new Error(
        `generate-zod: only local refs are supported, got ${ref}. A remote ref ` +
          `would be fetched at build time and pin the contract to the network.`,
      )
    }
    if (seen.includes(ref)) {
      throw new Error(
        `generate-zod: ref cycle ${[...seen, ref].join(' -> ')}. Inlining would ` +
          `not terminate; express the recursion with a zod lazy schema by hand.`,
      )
    }
    const target = ref
      .slice(2)
      .split('/')
      .map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'))
      .reduce((node, part) => {
        if (node === undefined || node === null) return undefined
        return node[part]
      }, root)
    if (target === undefined) {
      throw new Error(`generate-zod: unresolvable ref ${ref}`)
    }
    // Sibling keywords beside a `$ref` (e.g. a local `description`) win, per
    // 2020-12 semantics.
    const { $ref: _drop, ...siblings } = schema
    return inlineLocalRefs({ ...target, ...siblings }, root, [...seen, ref])
  }

  const out = {}
  for (const [key, value] of Object.entries(schema)) {
    if (key === '$defs') continue
    out[key] = inlineLocalRefs(value, root, seen)
  }
  return out
}

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '../../..')
const outDir = resolve(here, '../src/generated')

const schemas = [
  { input: 'map-config.schema.json', output: 'map-config.ts', exportName: 'MapConfigSchema' },
  { input: 'user-doc.schema.json', output: 'user-doc.ts', exportName: 'UserDocSchema' },
]

await mkdir(outDir, { recursive: true })

for (const s of schemas) {
  const raw = await readFile(resolve(repoRoot, 'contracts', s.input), 'utf8')
  const schema = inlineLocalRefs(JSON.parse(raw))
  const zodSrc = jsonSchemaToZod(schema, { name: s.exportName, module: 'esm' })
  const banner = `// AUTO-GENERATED from contracts/${s.input}. Do not edit by hand. Run \`pnpm --filter @warden/contracts build\`.\n\n`
  await writeFile(resolve(outDir, s.output), banner + zodSrc, 'utf8')
  console.info(`generated ${s.output}`)
}
