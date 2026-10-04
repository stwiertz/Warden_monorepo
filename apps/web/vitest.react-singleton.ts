// Pins every Node-side `require('react')` / `require('react/...')` to apps/web's own React.
//
// Why: the root .npmrc sets node-linker=hoisted (required by Expo/Metro in apps/mobile), so
// mobile's react@19.1.0 is hoisted to the repo root while web's react@19.2.4 is nested in
// apps/web/node_modules. Root-hoisted packages that web tests load (react-dom, next,
// @testing-library/react, @base-ui/react, ...) then `require('react')` from the root and get
// the second copy — hooks crash with "Cannot read properties of null (reading 'useState')".
// Vite's resolve.dedupe cannot help: those requires happen inside externalized CJS, outside
// Vite's resolver. This must run before anything imports React (first entry in setupFiles).
import Module from 'node:module'
import path from 'node:path'

const webRoot = path.resolve(__dirname)

type ResolveFilename = (
  request: string,
  parent: unknown,
  isMain: boolean,
  options?: unknown,
) => string

const mod = Module as unknown as { _resolveFilename: ResolveFilename & { __webReactPinned?: true } }

// setupFiles re-run per test file; a reused worker must not stack a wrapper each time.
if (!mod._resolveFilename.__webReactPinned) {
  const original = mod._resolveFilename
  const pinned: ResolveFilename & { __webReactPinned?: true } = function (
    this: unknown,
    request,
    parent,
    isMain,
    options,
  ) {
    if (request === 'react' || request.startsWith('react/')) {
      const merged = { ...(options as object | undefined), paths: [webRoot] }
      return original.call(this, request, parent, isMain, merged)
    }
    return original.call(this, request, parent, isMain, options)
  }
  pinned.__webReactPinned = true
  mod._resolveFilename = pinned
}
