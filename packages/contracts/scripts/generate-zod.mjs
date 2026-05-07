// Reads contracts/*.schema.json and emits zod modules into src/generated/.
// Runs as part of `pnpm --filter @warden/contracts build`.
//
// Why: the schemas in contracts/ are the cross-language source of truth (Python tooling
// validates emitted JSON against them, TS apps need typed runtime parsers). Re-generating
// from JSON Schema keeps both sides locked to the same shape.

import { jsonSchemaToZod } from 'json-schema-to-zod'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

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
  const schema = JSON.parse(raw)
  const zodSrc = jsonSchemaToZod(schema, { name: s.exportName, module: 'esm' })
  const banner = `// AUTO-GENERATED from contracts/${s.input}. Do not edit by hand. Run \`pnpm --filter @warden/contracts build\`.\n\n`
  await writeFile(resolve(outDir, s.output), banner + zodSrc, 'utf8')
  console.info(`generated ${s.output}`)
}
