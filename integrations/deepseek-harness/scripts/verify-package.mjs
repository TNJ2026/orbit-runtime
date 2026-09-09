import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
const packageJson = JSON.parse(await readFile(new URL('package.json', root), 'utf8'))
const publishedFiles = new Set([...packageJson.files, 'package.json'])

function exportTargets(value) {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(exportTargets)
  if (value && typeof value === 'object') {
    return Object.values(value).flatMap(exportTargets)
  }
  return []
}

for (const target of exportTargets(packageJson.exports)) {
  assert.match(target, /^\.\//, `export target ${target} must be package-relative`)
  assert.ok(
    publishedFiles.has(target.slice(2)),
    `export target ${target} must be included in files`,
  )
}

for (const group of [
  'dependencies', 'optionalDependencies', 'peerDependencies', 'devDependencies',
]) {
  for (const [name, version] of Object.entries(packageJson[group] ?? {})) {
    assert.doesNotMatch(
      String(version),
      /^(?:file|link|workspace):/,
      `${group}.${name} must be installable from the npm registry`,
    )
  }
}

for (const path of ['lib/index.js', 'lib/index.d.ts', 'lib/client.js']) {
  const output = await readFile(new URL(path, root), 'utf8')
  assert.doesNotMatch(
    output,
    /@orbit-runtime\/integration-core/,
    `${path} must inline @orbit-runtime/integration-core`,
  )
}

// The Harness loader reaches the entry through a plain `import()`, so the
// published chunk has to be syntax Node parses on its own. Standard decorators
// are the way this breaks silently: the bundler emits them verbatim, build and
// unit tests stay green, and the entry fails at profile boot instead.
try {
  await import(new URL('lib/index.js', root).href)
} catch (error) {
  assert.fail(`lib/index.js must load under a plain import(): ${error.message}`)
}

console.log('npm package is self-contained')
