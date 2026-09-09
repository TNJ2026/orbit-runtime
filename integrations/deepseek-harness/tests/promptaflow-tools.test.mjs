import assert from 'node:assert/strict'
import test from 'node:test'

import { PromptaFlowToolBridge } from '../lib/promptaflow-tools.js'

function fixture() {
  const definitions = new Map(), calls = [], watched = []
  const tools = { register(definition) { definitions.set(definition.name, definition); return () => definitions.delete(definition.name) } }
  const workspaceRegistry = { async resolveByPath(path) { return { id: 'workspace:1', path } } }
  const ctx = { get(name) { return name === 'tools' ? tools : workspaceRegistry } }
  const gateway = {
    async call(workspace, sessionId, name, args) {
      calls.push({ workspace, sessionId, name, args })
      if (name === 'start_run') return { run_id: 'run:1' }
      if (name === 'generate_workflow') return { job_id: 'job:1', status: 'queued', prompt: args.prompt }
      return { ok: true }
    },
    async run(workspace, sessionId, runId) {
      calls.push({ workspace, sessionId, name: 'inspect_run', args: { run_id: runId } })
      return { run_id: runId, allowed_commands: [{ command: 'langgraph_run.cancel', expected_version: 7 }] }
    },
  }
  new PromptaFlowToolBridge(ctx, gateway, (workspace, sessionId, job) => {
    watched.push({ workspace, sessionId, job })
  }).register()
  const exec = { signal: new AbortController().signal, agent: { session: { id: 'session:abc', header: { cwd: '/workspace' } } } }
  return { definitions, calls, exec, watched }
}

test('registers the bounded PromptaFlow MCP tool surface', () => {
  const { definitions } = fixture()
  assert.deepEqual([...definitions.keys()], [
    'promptaflow_list_workflows', 'promptaflow_list_runs', 'promptaflow_list_delegations',
    'promptaflow_claim_delegation', 'promptaflow_renew_delegation',
    'promptaflow_complete_delegation', 'promptaflow_reconcile_delegation', 'promptaflow_inspect_run',
    'promptaflow_start_run', 'promptaflow_generate_workflow', 'promptaflow_get_authoring_job',
    'promptaflow_cancel_run', 'promptaflow_resume_run',
  ])
})

test('delegation tools bind leases to the current Harness Session', async () => {
  const { definitions, calls, exec } = fixture()
  await definitions.get('promptaflow_list_delegations').execute({}, exec)
  await definitions.get('promptaflow_claim_delegation').execute({}, exec)
  await definitions.get('promptaflow_renew_delegation').execute({ delegation_id: 'd:1' }, exec)
  await definitions.get('promptaflow_complete_delegation').execute({
    delegation_id: 'd:1', result: { answer: 'done' },
  }, exec)

  assert.deepEqual(calls.map(call => call.name), [
    'list_delegations', 'claim_delegation', 'renew_delegation',
    'complete_delegation',
  ])
  for (const call of calls.slice(1)) {
    assert.equal(call.args.worker_id, 'harness-session:session:abc')
  }
})

test('generate owns idempotency and tells the panel before it answers', async () => {
  // The panel is a person watching; the return value is the model's next turn.
  // Telling the model first would leave a person looking at a still panel for
  // as long as the Agent takes to say something.
  const { definitions, calls, exec, watched } = fixture()
  const job = await definitions.get('promptaflow_generate_workflow')
    .execute({ prompt: '  clean the CSV  ', agent: 'codex' }, exec)

  assert.equal(job.job_id, 'job:1')
  assert.equal(calls[0].name, 'generate_workflow')
  assert.equal(calls[0].sessionId, 'session:abc')
  assert.equal(calls[0].args.agent, 'codex')
  assert.match(calls[0].args.idempotency_key, /^[0-9a-f-]{36}$/)
  assert.deepEqual(watched.map(item => item.job.job_id), ['job:1'])
  assert.equal(watched[0].sessionId, 'session:abc')
  assert.equal(watched[0].workspace.canonicalPath, '/workspace')
})

test('the Agent is the Runtime\'s choice unless the caller named one', async () => {
  const { definitions, calls, exec } = fixture()
  await definitions.get('promptaflow_generate_workflow').execute({ prompt: 'anything' }, exec)
  assert.equal('agent' in calls[0].args, false)
})

test('start routes through Session Workspace and owns idempotency', async () => {
  const { definitions, calls, exec } = fixture()
  const result = await definitions.get('promptaflow_start_run').execute({ workflow_id: 'wf', goal: 'ship it' }, exec)
  assert.equal(result.run_id, 'run:1')
  assert.equal(calls[0].workspace.id, 'workspace:1')
  assert.equal(calls[0].sessionId, 'session:abc')
  assert.equal(calls[0].name, 'start_run')
  assert.equal(calls[0].args.wait, false)
  assert.match(calls[0].args.idempotency_key, /^[0-9a-f-]{36}$/)
})

test('cancel re-reads advertised command and revision before mutation', async () => {
  const { definitions, calls, exec } = fixture()
  await definitions.get('promptaflow_cancel_run').execute({ run_id: 'run:1' }, exec)
  assert.deepEqual(calls.map(call => call.name), ['inspect_run', 'cancel_run'])
  assert.equal(calls[1].args.expected_version, 7)
  assert.match(calls[1].args.idempotency_key, /^[0-9a-f-]{36}$/)
})

test('tool execution refuses calls without a live Agent Session cwd', async () => {
  const { definitions, exec } = fixture()
  await assert.rejects(definitions.get('promptaflow_list_runs').execute({}, { ...exec, agent: undefined }), /live Harness Agent Session/)
  await assert.rejects(definitions.get('promptaflow_list_runs').execute({}, { ...exec, agent: { session: { id: 'x', header: {} } } }), /Workspace cwd/)
})
