import assert from 'node:assert/strict'
import { execFile, spawn } from 'node:child_process'
import { mkdtemp, mkdir, realpath, rm } from 'node:fs/promises'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

import { PromptaFlowGateway } from '../lib/gateway.js'

const here = dirname(fileURLToPath(import.meta.url))
const promptaflow = process.env.PROMPTAFLOW_BIN || resolve(
  here,
  process.platform === 'win32' ? '../../../.venv/Scripts/paf.exe' : '../../../.venv/bin/paf',
)
const execFileAsync = promisify(execFile)

async function freePort() {
  const server = createServer()
  await new Promise(resolveReady => server.listen(0, '127.0.0.1', resolveReady))
  const port = server.address().port
  await new Promise((resolveClosed, reject) => server.close(error => error ? reject(error) : resolveClosed()))
  return port
}

async function waitReady(url, child) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error(`PromptaFlow Hub exited with ${String(child.exitCode)}`)
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise(resolveWait => setTimeout(resolveWait, 50))
  }
  throw new Error('PromptaFlow Hub did not become ready')
}

async function stop(child) {
  if (child.exitCode !== null) return
  child.kill('SIGTERM')
  await new Promise(resolveExit => child.once('exit', resolveExit))
}

async function runtimePid(workspacePath) {
  const canonicalWorkspace = await realpath(workspacePath)
  for (let attempt = 0; attempt < 100; attempt++) {
    const { stdout } = await execFileAsync(promptaflow, ['runtimes', '--json'], {
      cwd: workspacePath, encoding: 'utf8', timeout: 5_000,
    })
    const runtimes = JSON.parse(stdout)
    assert.ok(Array.isArray(runtimes), 'paf runtimes --json must return an array')
    const runtime = runtimes.find(runtime =>
      runtime?.project_root && String(runtime.project_root) === canonicalWorkspace,
    )
    if (runtime !== undefined) {
      assert.equal(Number.isInteger(runtime.pid), true, 'Runtime discovery must publish its PID')
      return runtime.pid
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 50))
  }
  throw new Error(`PromptaFlow Runtime was not discovered for ${workspacePath}`)
}

async function waitPidGone(pid) {
  for (let attempt = 0; attempt < 100; attempt++) {
    try { process.kill(pid, 0) }
    catch (error) {
      if (error?.code === 'ESRCH') return
      throw error
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 50))
  }
  throw new Error(`PromptaFlow Runtime process ${String(pid)} remained alive after Hub exit`)
}

test('Harness reaches its workspace Runtime through the fixed Hub', { timeout: 30_000 }, async t => {
  const root = await mkdtemp(join(tmpdir(), 'promptaflow-independent-e2e-'))
  // Acquiring a Workspace runs
  // `paf hub register`, which writes the machine-wide workspace registry —
  // so without this every run of this test left its throwaway directory in the
  // developer's real one, and nothing ever took it out. Redirecting the Hub
  // state beats
  // deregistering in teardown: a run that dies half way leaves nothing behind
  // either.
  const overrides = { PROMPTAFLOW_HUB_ROOT: join(root, 'hub') }
  const previous = Object.fromEntries(
    Object.keys(overrides).map(name => [name, process.env[name]]),
  )
  Object.assign(process.env, overrides)
  const workspacePath = join(root, 'workspace')
  await mkdir(workspacePath)
  const port = await freePort()
  const child = spawn(promptaflow, [
    'hub', 'serve', '--host', '127.0.0.1', '--port', String(port),
  ], { cwd: workspacePath, stdio: ['ignore', 'ignore', 'pipe'] })
  let ownedRuntimePid
  let stderr = ''
  child.stderr.setEncoding('utf8'); child.stderr.on('data', chunk => { stderr += chunk })
  t.after(async () => {
    try {
      await stop(child)
      if (ownedRuntimePid !== undefined) {
        try { await waitPidGone(ownedRuntimePid) }
        catch (error) { throw new Error(`${String(error)}\n${stderr}`) }
      }
    } finally {
      for (const [name, value] of Object.entries(previous)) {
        if (value === undefined) delete process.env[name]
        else process.env[name] = value
      }
      await rm(root, { recursive: true, force: true })
    }
  })
  const base = `http://127.0.0.1:${String(port)}`
  try { await waitReady(`${base}/health/ready`, child) }
  catch (error) { throw new Error(`${String(error)}\n${stderr}`) }

  const gateway = new PromptaFlowGateway(promptaflow, [], globalThis.fetch, root, base)
  const workspace = { id: 'workspace:e2e', canonicalPath: workspacePath }
  const release = await gateway.acquire(workspace, true)
  const first = await gateway.call(workspace, 'first', 'list_runs', {})
  ownedRuntimePid = await runtimePid(workspacePath)
  const second = await gateway.call(workspace, 'second', 'list_runs', {})
  assert.deepEqual(first.runs, [])
  assert.deepEqual(second.runs, [])
  await release()

  // What `/promptaflow` opens stays on the stable Hub namespace.
  const ui = await gateway.uiUrl(workspace)
  assert.match(ui, new RegExp(`^${base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/workspaces/[a-f0-9]{12}/ui/$`))
  assert.equal((await fetch(ui)).ok, true)
  assert.equal((await fetch(`${base}/health/ready`)).ok, true)
  assert.equal(child.exitCode, null)
})
