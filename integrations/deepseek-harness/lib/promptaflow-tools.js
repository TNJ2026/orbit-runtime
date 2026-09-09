const JSON_OUTPUT = {
    schema: {},
    render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
};
const object = (properties, required = []) => ({
    type: 'object', properties, ...(required.length ? { required } : {}), additionalProperties: false,
});
function args(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value))
        throw new Error('PromptaFlow tool arguments must be an object');
    return value;
}
export class PromptaFlowToolBridge {
    ctx;
    gateway;
    watch;
    tools;
    registry;
    constructor(ctx, gateway, watch = () => { }) {
        this.ctx = ctx;
        this.gateway = gateway;
        this.watch = watch;
        this.tools = ctx.get('tools');
        this.registry = ctx.get('workspaceRegistry');
    }
    register() {
        for (const definition of this.definitions())
            this.tools.register(definition);
    }
    definitions() {
        return [
            this.definition('promptaflow_list_workflows', 'List published PromptaFlow workflows available in this Session Workspace.', object({ ready_only: { type: 'boolean' } }), 'list_workflows', true),
            this.definition('promptaflow_list_runs', 'List PromptaFlow workflow runs owned by this Harness Session.', object({ status: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 200 } }), 'list_runs', true),
            this.definition('promptaflow_list_delegations', 'Check once on the first turn of this Session for resumable PromptaFlow Agent work. Stay silent when the returned list is empty.', object({
                statuses: { type: 'array', items: { type: 'string' }, maxItems: 6 },
                limit: { type: 'integer', minimum: 1, maximum: 200 },
            }), 'list_delegations', true),
            {
                name: 'promptaflow_claim_delegation',
                description: 'Claim the next queued PromptaFlow Agent step for this Harness Session.',
                parameters: object({ lease_seconds: { type: 'integer', minimum: 5, maximum: 300 } }),
                output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value), { workspace, session } = await this.route(exec);
                    return await this.gateway.call(workspace, String(session.id), 'claim_delegation', {
                        worker_id: `harness-session:${String(session.id)}`,
                        ...(input.lease_seconds === undefined ? {} : { lease_seconds: input.lease_seconds }),
                    });
                },
            },
            {
                name: 'promptaflow_renew_delegation',
                description: 'Renew an PromptaFlow Agent-step lease held by this Harness Session.',
                parameters: object({
                    delegation_id: { type: 'string' },
                    lease_seconds: { type: 'integer', minimum: 5, maximum: 300 },
                }, ['delegation_id']), output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value), { workspace, session } = await this.route(exec);
                    return await this.gateway.call(workspace, String(session.id), 'renew_delegation', {
                        delegation_id: input.delegation_id,
                        worker_id: `harness-session:${String(session.id)}`,
                        ...(input.lease_seconds === undefined ? {} : { lease_seconds: input.lease_seconds }),
                    });
                },
            },
            {
                name: 'promptaflow_complete_delegation',
                description: 'Return exactly one result object or error for an PromptaFlow Agent step.',
                parameters: object({
                    delegation_id: { type: 'string' }, result: { type: 'object' },
                    error: { type: 'string' },
                }, ['delegation_id']), output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value), { workspace, session } = await this.route(exec);
                    return await this.gateway.call(workspace, String(session.id), 'complete_delegation', {
                        ...input, worker_id: `harness-session:${String(session.id)}`,
                    });
                },
            },
            this.definition('promptaflow_reconcile_delegation', 'Submit a user-verified outcome for unknown PromptaFlow Agent work; never execute unknown work again.', object({
                delegation_id: { type: 'string' },
                outcome: { type: 'string', enum: ['confirmed_succeeded', 'confirmed_failed'] },
                note: { type: 'string' }, result: { type: 'object' }, error: { type: 'string' },
                idempotency_key: { type: 'string' },
            }, ['delegation_id', 'outcome', 'idempotency_key']), 'reconcile_delegation', false),
            this.definition('promptaflow_inspect_run', 'Inspect one PromptaFlow Run, including status, revision, interrupts and allowed commands.', object({ run_id: { type: 'string' } }, ['run_id']), 'inspect_run', true),
            {
                name: 'promptaflow_start_run',
                description: 'Start a published PromptaFlow workflow in the current Workspace. Returns immediately so progress appears in the PromptaFlow Run Card.',
                parameters: object({
                    workflow_id: { type: 'string' }, workflow_version: { type: 'integer' },
                    input: { type: 'object' }, goal: { type: 'string', maxLength: 4000 },
                }, ['workflow_id']), output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value);
                    return await this.call(exec, 'start_run', {
                        ...input, wait: false, idempotency_key: crypto.randomUUID(),
                    });
                },
            },
            {
                name: 'promptaflow_generate_workflow',
                description: 'Draft a new PromptaFlow workflow from a description and publish it if the compiler accepts it. '
                    + 'Returns a job immediately — authoring takes a while — so poll promptaflow_get_authoring_job '
                    + 'with the job_id until its status leaves queued/running. Nothing is published until the '
                    + 'compiler accepts the draft, so a failed job has changed nothing. Progress also appears '
                    + 'in the PromptaFlow panel.',
                parameters: object({
                    prompt: { type: 'string', maxLength: 4000 },
                    agent: { type: 'string', description: 'Which Agent writes it; the Runtime picks one if omitted.' },
                }, ['prompt']), output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value);
                    const { workspace, session } = await this.route(exec);
                    const job = await this.gateway.call(workspace, String(session.id), 'generate_workflow', {
                        prompt: String(input.prompt),
                        ...(input.agent === undefined ? {} : { agent: String(input.agent) }),
                        idempotency_key: crypto.randomUUID(),
                    });
                    // The panel is told before the model is: a person watching it should
                    // not have to wait for the Agent's next turn to learn work started.
                    this.watch(workspace, String(session.id), job);
                    return job;
                },
            },
            this.definition('promptaflow_get_authoring_job', 'Check an PromptaFlow authoring job started by promptaflow_generate_workflow. Status queued or running '
                + 'means it is still going; done carries the published workflow, failed carries why.', object({ job_id: { type: 'string' } }, ['job_id']), 'get_authoring_job', true),
            {
                name: 'promptaflow_cancel_run',
                description: 'Cancel an PromptaFlow Run if its latest server-advertised commands allow cancellation.',
                parameters: object({ run_id: { type: 'string' } }, ['run_id']), output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const runId = String(args(value).run_id);
                    return await this.command(exec, runId, 'langgraph_run.cancel');
                },
            },
            {
                name: 'promptaflow_resume_run',
                description: 'Resume an interrupted PromptaFlow Run using its latest server-advertised revision.',
                parameters: object({ run_id: { type: 'string' }, value: {}, interrupt_id: { type: 'string' } }, ['run_id']),
                output: JSON_OUTPUT, timeoutMs: 60_000,
                execute: async (value, exec) => {
                    const input = args(value), runId = String(input.run_id);
                    return await this.command(exec, runId, 'langgraph_run.resume', input.value, input.interrupt_id);
                },
            },
        ];
    }
    definition(name, description, parameters, wireName, concurrencySafe) {
        return {
            name, description, parameters, output: JSON_OUTPUT, timeoutMs: 60_000,
            isConcurrencySafe: concurrencySafe ? () => true : undefined,
            execute: async (value, exec) => await this.call(exec, wireName, args(value)),
        };
    }
    async command(exec, runId, command, value, interruptId) {
        const { workspace, session } = await this.route(exec);
        const run = await this.gateway.run(workspace, String(session.id), runId);
        const advertised = run.allowed_commands.find(item => item.command === command);
        if (!advertised)
            throw new Error(`PromptaFlow no longer advertises ${command} for Run ${runId}`);
        return await this.gateway.call(workspace, String(session.id), command === 'langgraph_run.cancel' ? 'cancel_run' : 'resume_run', {
            run_id: runId, expected_version: advertised.expected_version,
            idempotency_key: crypto.randomUUID(), ...(value === undefined ? {} : { value }),
            ...(interruptId === undefined ? {} : { interrupt_id: interruptId }),
        });
    }
    async call(exec, name, input) {
        const { workspace, session } = await this.route(exec);
        return await this.gateway.call(workspace, String(session.id), name, input);
    }
    async route(exec) {
        const session = exec.agent?.session;
        if (!session)
            throw new Error('PromptaFlow tools require a live Harness Agent Session');
        const cwd = session.header.cwd;
        if (!cwd)
            throw new Error('PromptaFlow tools require the Session to have a Workspace cwd');
        const registered = await this.registry.resolveByPath(cwd);
        return { session, workspace: {
                id: registered ? String(registered.id) : `cwd:${cwd}`,
                canonicalPath: registered?.path ?? cwd,
            } };
    }
}
