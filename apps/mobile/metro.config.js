// Expo + pnpm monorepo Metro config.
// Validated against Expo SDK 54 / RN 0.81 / pnpm 9.12 with .npmrc node-linker=hoisted.
// See https://docs.expo.dev/guides/monorepos/ for canonical reference.

const { getDefaultConfig } = require('expo/metro-config')
const { withNativeWind } = require('nativewind/metro')
const path = require('path')

const projectRoot = __dirname
const monorepoRoot = path.resolve(projectRoot, '../..')

const config = getDefaultConfig(projectRoot)

// Watch the monorepo root so changes in packages/* and contracts/* reflow Metro.
config.watchFolders = [monorepoRoot]

// Force Metro to resolve modules from this app's node_modules and the monorepo root,
// rather than walking up the dir tree (which would find unrelated copies in pnpm's store).
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(monorepoRoot, 'node_modules'),
]
config.resolver.disableHierarchicalLookup = true

module.exports = withNativeWind(config, { input: './global.css' })
