/**
 * Browser client bundle, mirroring the DeepSeek Harness `clientBundle`
 * protocol: a CJS closure-factory artifact registered through
 * `window.__ModuleLoader__.load`, whose externals resolve from the loader's
 * frozen module table, with CSS Modules compiled by lightningcss and injected
 * as a `<style data-plugin>` tag when the factory runs.
 */

import { readFileSync } from 'node:fs'
import { basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { transform } from 'lightningcss'
import { defineConfig } from 'tsdown'
import ts from 'typescript'

/**
 * Downlevel standard decorators in the emitted server chunk.
 *
 * `@Remote` is a standard (TC39) decorator, and Rolldown's own decorator
 * transform implements only the legacy proposal — so it passes `@Remote(...)`
 * through verbatim, and the published `lib/index.js` is then syntax no Node
 * release can parse: the Harness loader fails the entry at boot with
 * `Invalid or unexpected token`, long after a green build and a green test
 * run. TypeScript is the transform that understands the standard proposal,
 * so the chunk goes back through it before it is written.
 */
const downlevelDecorators = {
  name: 'downlevel-standard-decorators',
  renderChunk(code: string) {
    // Cheap guard: a chunk with no decorator line is left byte-identical, so
    // this never rewrites the client or types builds by accident.
    if (!/^\s*@[A-Za-z_$]/m.test(code)) return null
    const { outputText } = ts.transpileModule(code, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.ESNext,
        experimentalDecorators: false,
      },
      fileName: 'chunk.ts',
    })
    return { code: outputText }
  },
}

/** Platform seed entries the browser module table answers (external). */
const PLATFORM_MODULES = [
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client',
  '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-ui-primitives',
]
/**
 * Dynamic rows whose factories the shell preloads before boot. Empty: this
 * bundle reaches the platform through `ctx` alone, and the one row that used
 * to sit here (`@deepseek-ai/dsh-client-runtime/client`) is a package the
 * Harness split up — its ClientContext seats now come from ui-renderer, and
 * they are type-only, so nothing survives erasure to be resolved at runtime.
 */
const PRELOADED: readonly string[] = []
const CLIENT_EXTERNALS: readonly string[] = [...PLATFORM_MODULES, ...PRELOADED]

/**
 * Resolve the shared integration layer from source so this package can inline
 * it without depending on an unpublished workspace package.
 */
const ORBIT_CORE_ENTRY = fileURLToPath(
  new URL('../../integration-core/src/index.ts', import.meta.url),
)
const ORBIT_CORE_TYPES = fileURLToPath(
  new URL('../../integration-core/src/types.ts', import.meta.url),
)
const ORBIT_CORE_ALIAS = { '@orbit-runtime/integration-core': ORBIT_CORE_ENTRY }

/** Wire/type layers a client bundle may inline (no shared runtime identity). */
const INLINE_SAFE = /^@deepseek-ai\/dsh-(session|tools|brand)(\/|$)/

const CSS_VIRTUAL_PREFIX = '\0dsh-css:'
const CSS_VIRTUAL_SUFFIX = '.mjs'

/** The id the host looks this bundle up by: the package name, read not restated. */
const PLUGIN_ID: string = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
).name

export default defineConfig([{
  name: `${PLUGIN_ID}/server`,
  entry: { index: 'src/index.ts' },
  plugins: [downlevelDecorators],
  tsconfig: 'tsconfig.bundle.json',
  outDir: 'lib',
  format: 'esm',
  platform: 'node',
  target: 'node22',
  fixedExtension: false,
  dts: true,
  sourcemap: false,
  clean: false,
  codeSplitting: false,
  alias: ORBIT_CORE_ALIAS,
  deps: {
    // Host and Node dependencies stay external; integration-core resolves to
    // local source through the alias above and is therefore bundled.
    neverBundle: true,
    alwaysBundle: /^@orbit-runtime\/integration-core$/,
    dts: {
      neverBundle: true,
      alwaysBundle: /^@orbit-runtime\/integration-core$/,
    },
  },
}, {
  name: `${PLUGIN_ID}/types`,
  entry: { types: ORBIT_CORE_TYPES },
  tsconfig: 'tsconfig.bundle.json',
  outDir: 'lib',
  format: 'esm',
  platform: 'node',
  target: 'node22',
  fixedExtension: false,
  dts: true,
  sourcemap: false,
  clean: false,
  codeSplitting: false,
  deps: {
    neverBundle: true,
    alwaysBundle: /^@orbit-runtime\/integration-core$/,
    dts: {
      neverBundle: true,
      alwaysBundle: /^@orbit-runtime\/integration-core$/,
    },
  },
}, {
  name: `${PLUGIN_ID}/client`,
  entry: { client: 'src/client/index.tsx' },
  tsconfig: 'tsconfig.client.json',
  outDir: 'lib',
  format: 'cjs',
  platform: 'browser',
  target: 'es2022',
  dts: false,
  sourcemap: true,
  clean: false,
  alias: ORBIT_CORE_ALIAS,
  deps: {
    neverBundle: (id: string) => CLIENT_EXTERNALS.includes(id),
    alwaysBundle: (id: string) => !CLIENT_EXTERNALS.includes(id),
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV ?? 'production'),
  },
  plugins: [{
    name: 'dsh-client-bundle-purity',
    resolveId(source: string) {
      if (!source.startsWith('@deepseek-ai/')) return null
      if (CLIENT_EXTERNALS.includes(source)) return null
      if (INLINE_SAFE.test(source)) return null
      throw new Error(
        `client bundle purity: "${source}" is not a platform module nor an inline-safe wire layer — `
        + 'cross-plugin value imports would either duplicate a runtime instance or ask the frozen '
        + 'module table for a specifier it cannot answer (type-only imports are erased and never reach this gate)',
      )
    },
  }, {
    name: 'dsh-css-inline',
    resolveId(source: string, importer: string | undefined) {
      if (!source.endsWith('.css')) return null
      let abs: string
      if (source.startsWith('.') && importer !== undefined) {
        abs = fileURLToPath(new URL(source, `file://${importer}`))
      } else if (source.startsWith('/')) {
        abs = source
      } else {
        abs = fileURLToPath(import.meta.resolve(source))
      }
      return CSS_VIRTUAL_PREFIX + abs + CSS_VIRTUAL_SUFFIX
    },
    load(virtualId: string) {
      if (!virtualId.startsWith(CSS_VIRTUAL_PREFIX)) return null
      const fileId = virtualId.slice(CSS_VIRTUAL_PREFIX.length, -CSS_VIRTUAL_SUFFIX.length)
      const isModule = fileId.endsWith('.module.css')
      const { code, exports: cssExports } = transform({
        filename: fileId, code: readFileSync(fileId),
        cssModules: isModule ? { pattern: '[hash]_[local]' } : undefined, minify: true,
      })
      // Sorted so the emitted map is byte-stable: lightningcss does not promise
      // an export order, and an unstable one rewrites lib/client.js on every
      // build — diff noise in a repository that commits its build output.
      const classMap: Record<string, string> = {}
      for (const [local, exported] of Object.entries(cssExports ?? {}).sort(
        ([a], [b]) => (a < b ? -1 : a > b ? 1 : 0),
      )) classMap[local] = exported.name
      const tagId = `${PLUGIN_ID}/${basename(fileId)}`
      return [
        `const css = ${JSON.stringify(code.toString())};`,
        `const tagId = ${JSON.stringify(tagId)};`,
        "if (typeof document !== 'undefined' && document.querySelector('style[data-plugin-css=' + JSON.stringify(tagId) + ']') === null) {",
        "  const tag = document.createElement('style');",
        `  tag.dataset.plugin = ${JSON.stringify(PLUGIN_ID)};`,
        '  tag.dataset.pluginCss = tagId;',
        '  tag.textContent = css;',
        '  document.head.appendChild(tag);',
        '}',
        `export default ${JSON.stringify(classMap)};`,
      ].join('\n')
    },
  }],
  outputOptions: {
    entryFileNames: 'client.js',
    banner: `window.__ModuleLoader__.load({ id: ${JSON.stringify(PLUGIN_ID)}, factory: (require) => {`,
    footer: 'return module.exports; } });',
    intro: 'var module = { exports: {} }; var exports = module.exports;',
  },
}])
