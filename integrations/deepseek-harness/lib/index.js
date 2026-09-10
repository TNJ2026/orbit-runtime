var __runInitializers = this && this.__runInitializers || function(thisArg, initializers, value) {
	var useValue = arguments.length > 2;
	for (var i = 0; i < initializers.length; i++) value = useValue ? initializers[i].call(thisArg, value) : initializers[i].call(thisArg);
	return useValue ? value : void 0;
};
var __esDecorate = this && this.__esDecorate || function(ctor, descriptorIn, decorators, contextIn, initializers, extraInitializers) {
	function accept(f) {
		if (f !== void 0 && typeof f !== "function") throw new TypeError("Function expected");
		return f;
	}
	var kind = contextIn.kind, key = kind === "getter" ? "get" : kind === "setter" ? "set" : "value";
	var target = !descriptorIn && ctor ? contextIn["static"] ? ctor : ctor.prototype : null;
	var descriptor = descriptorIn || (target ? Object.getOwnPropertyDescriptor(target, contextIn.name) : {});
	var _, done = false;
	for (var i = decorators.length - 1; i >= 0; i--) {
		var context = {};
		for (var p in contextIn) context[p] = p === "access" ? {} : contextIn[p];
		for (var p in contextIn.access) context.access[p] = contextIn.access[p];
		context.addInitializer = function(f) {
			if (done) throw new TypeError("Cannot add initializers after decoration has completed");
			extraInitializers.push(accept(f || null));
		};
		var result = (0, decorators[i])(kind === "accessor" ? {
			get: descriptor.get,
			set: descriptor.set
		} : descriptor[key], context);
		if (kind === "accessor") {
			if (result === void 0) continue;
			if (result === null || typeof result !== "object") throw new TypeError("Object expected");
			if (_ = accept(result.get)) descriptor.get = _;
			if (_ = accept(result.set)) descriptor.set = _;
			if (_ = accept(result.init)) initializers.unshift(_);
		} else if (_ = accept(result)) {
			if (kind === "field") initializers.unshift(_);
			else descriptor[key] = _;
		}
	}
	if (target) Object.defineProperty(target, contextIn.name, descriptor);
	done = true;
};
var __setFunctionName = this && this.__setFunctionName || function(f, name, prefix) {
	if (typeof name === "symbol") name = name.description ? "[".concat(name.description, "]") : "";
	return Object.defineProperty(f, "name", {
		configurable: true,
		value: prefix ? "".concat(prefix, " ", name) : name
	});
};
import { Remote, TypertRemoteService } from "@deepseek-ai/dsh-typert-protocol";
import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { mkdir, open, realpath, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { createUserMessage } from "@deepseek-ai/dsh-llm";
//#region ../../integration-core/src/artifact-export.ts
/** Handing an Artifact over as a file somebody can open.
*
* PromptaFlow keeps Artifacts in a content-addressed store: the file on disk is
* named by the sha256 of its own bytes, carries no extension, is shared by
* every Artifact with identical content, and is collected when nothing
* references it. It is a real path, and it is the wrong path to hand anybody —
* a person told "that is your file" will open it in an editor and save, and
* saving corrupts every Artifact that shares those bytes.
*
* So the bytes are copied out to an ordinary file instead: named for the
* Artifact, extended for its type, and belonging to the person rather than to
* the store. What they get back is a path they can double-click and a copy
* they are free to edit.
*/
/** What each recorded content type is called on a filesystem.
*
* Recorded, not sniffed. PromptaFlow wrote down what the workflow produced, and a
* guess made here would be a second opinion about the same bytes. */
const EXTENSIONS = {
	"text/markdown": ".md",
	"text/plain": ".txt",
	"text/html": ".html",
	"text/csv": ".csv",
	"application/json": ".json",
	"application/pdf": ".pdf",
	"image/png": ".png",
	"image/jpeg": ".jpg",
	"image/gif": ".gif",
	"image/svg+xml": ".svg"
};
/**
* The extension to save one Artifact under.
*
* The recorded name wins when there is one: a workflow that said what it was
* writing knows better than a table does. Then the content type. Then `.bin`,
* which is not a guess but a statement that nobody said.
*/
function artifactExtension(contentType, filename) {
	const named = typeof filename === "string" ? /\.[A-Za-z0-9]{1,8}$/.exec(filename) : null;
	if (named) return named[0].toLowerCase();
	const type = (contentType ?? "").split(";")[0]?.trim().toLowerCase() ?? "";
	return EXTENSIONS[type] ?? ".bin";
}
/**
* What the copy is called: the Artifact's own digest, shortened, plus a type.
*
* Named for the Artifact rather than for the Run or the moment, so exporting
* the same Artifact twice writes the same file rather than a second copy with
* a number after it — the bytes are identical by construction, since the name
* they came from *is* their hash.
*/
function artifactFilename(artifactId, contentType, filename) {
	return `promptaflow-${artifactId.replace(/^langgraph_artifact:/, "").replace(/[^A-Za-z0-9]/g, "").slice(0, 12) || "artifact"}${artifactExtension(contentType, filename)}`;
}
const READABLE_TYPES = ["text/markdown", "text/plain"];
/**
* Whether an Artifact should be read here or handed over as a file.
*
* Decided from what PromptaFlow recorded, before any bytes move: asking for a 2 MiB
* PDF in order to discover it is a 2 MiB PDF is the round trip this exists to
* avoid. Anything not plainly text, or not small, is a file — including the
* types a browser could render, because rendering someone else's HTML inside
* the panel's own page is not reading, it is hosting.
*/
function readableAsText(contentType, sizeBytes) {
	const type = (contentType ?? "").split(";")[0]?.trim().toLowerCase() ?? "";
	const size = typeof sizeBytes === "number" && Number.isFinite(sizeBytes) ? sizeBytes : Infinity;
	return READABLE_TYPES.includes(type) && size >= 0 && size < 2048;
}
//#endregion
//#region ../../integration-core/src/authoring-claim.ts
/** Writing a Workflow with the Agent that is already here.
*
* PromptaFlow will hand a generation prompt to a connected MCP client rather than
* fork an Agent CLI for it — but only to a client that has shown up on the
* queue. Being connected is not enough: the broker counts a client as present
* because it is *waiting for work*, not because it once called a tool. Nothing
* in this Host had ever waited, so PromptaFlow forked a CLI every time, and the
* Agent that wrote the Workflow was one nobody could see working.
*
* This is the waiting. The loop lives in the Host; the parts that decide what
* happens live here, taking their effects as arguments so the policy can be
* read and tested without a Runtime, a model, or a session.
*/
/** The name this Host is offered under in PromptaFlow's writer menu. */
const CLAIM_CLIENT = "harness";
/** Private, stable writer address for one Harness conversation. */
function authoringClientForSession(sessionId) {
	const digest = createHash("sha256").update(sessionId).digest("hex").slice(0, 24);
	return `route.${CLAIM_CLIENT}.${digest}`;
}
/** How long to leave the queue alone after a round that failed. Unrelated to
*  the wait: this is about a Runtime that is not answering, not about silence
*  on a queue that is. */
const CLAIM_RETRY_MS = 15e3;
/**
* One turn of the loop: wait, ask, answer.
*
* Whatever the model says is submitted, even when it does not look like a
* document. PromptaFlow extracts and compiles it exactly as it does a CLI's stdout,
* and a document it refuses comes back as a fresh request carrying the
* compiler's findings — so a chatty answer costs a round, not the job. Judging
* the answer here would be a second, worse copy of that validator.
*
* A failure to ask is not answered at all. Submitting something the model
* never said would publish a Workflow nobody wrote; leaving the request alone
* lets its lease lapse and puts it back on the queue, which is the outcome the
* broker already knows how to have.
*/
async function claimOnce(deps) {
	let claimed;
	try {
		claimed = await deps.wait(45);
	} catch (error) {
		deps.report("wait", error);
		return "failed";
	}
	if (claimed === null) return "idle";
	let answer;
	try {
		answer = await deps.ask(claimed.prompt);
	} catch (error) {
		deps.report("ask", error);
		return "failed";
	}
	if (!answer.trim()) {
		deps.report("ask", /* @__PURE__ */ new Error("the Agent produced no answer to submit"));
		return "failed";
	}
	try {
		await deps.submit(claimed.request_id, answer);
	} catch (error) {
		deps.report("submit", error);
		return "failed";
	}
	return "answered";
}
/**
* What the model said, out of the events a turn appended.
*
* Only `text` blocks of `assistant/message`. Reasoning blocks are the model
* thinking rather than answering, and tool calls are it doing something else
* entirely; including either would hand PromptaFlow a document with the working-out
* wrapped around it. Every message is taken, not the last, because a turn that
* used a tool answers across more than one.
*/
function answerFrom(events, afterIndex) {
	const parts = [];
	for (const event of events.slice(Math.max(0, afterIndex))) {
		if (event.type !== "assistant/message") continue;
		const content = event.data?.message?.content;
		if (!Array.isArray(content)) continue;
		for (const block of content) if (block?.type === "text" && typeof block.text === "string") parts.push(block.text);
	}
	return parts.join("\n");
}
//#endregion
//#region ../../integration-core/src/codecs.ts
function object$1(value, path) {
	if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error(`invalid PromptaFlow DTO at ${path}: expected object`);
	return value;
}
function string(value, path) {
	if (typeof value !== "string") throw new Error(`invalid PromptaFlow DTO at ${path}: expected string`);
	return value;
}
function number(value, path) {
	if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`invalid PromptaFlow DTO at ${path}: expected number`);
	return value;
}
function boolean(value, path) {
	if (typeof value !== "boolean") throw new Error(`invalid PromptaFlow DTO at ${path}: expected boolean`);
	return value;
}
function array(value, path) {
	if (!Array.isArray(value)) throw new Error(`invalid PromptaFlow DTO at ${path}: expected array`);
	return value;
}
function decodeRun(value) {
	const item = object$1(value, "run");
	for (const key of [
		"run_id",
		"goal",
		"workflow_id",
		"status",
		"created_at",
		"updated_at"
	]) string(item[key], `run.${key}`);
	for (const key of [
		"workflow_version",
		"revision",
		"artifact_count"
	]) number(item[key], `run.${key}`);
	array(item.interrupts, "run.interrupts");
	for (const [index, command] of array(item.allowed_commands, "run.allowed_commands").entries()) {
		const entry = object$1(command, `run.allowed_commands[${index}]`);
		string(entry.command, `run.allowed_commands[${index}].command`);
		number(entry.expected_version, `run.allowed_commands[${index}].expected_version`);
	}
	return item;
}
function decodeStep(value, index) {
	const item = object$1(value, `steps[${index}]`);
	string(item.node_id, `steps[${index}].node_id`);
	string(item.status, `steps[${index}].status`);
	if (item.has_output !== void 0) boolean(item.has_output, `steps[${index}].has_output`);
	if (item.resolution !== void 0 && item.resolution !== null) {
		const resolution = object$1(item.resolution, `steps[${index}].resolution`);
		if (string(resolution.kind, `steps[${index}].resolution.kind`) !== "reconciliation_required") throw new Error(`invalid PromptaFlow DTO at steps[${index}].resolution.kind`);
		if (resolution.delegation_id !== void 0 && resolution.delegation_id !== null) string(resolution.delegation_id, `steps[${index}].resolution.delegation_id`);
	}
	if (item.reconciliation !== void 0 && item.reconciliation !== null) {
		const decision = object$1(item.reconciliation, `steps[${index}].reconciliation`);
		const outcome = string(decision.outcome, `steps[${index}].reconciliation.outcome`);
		if (!["confirmed_succeeded", "confirmed_failed"].includes(outcome)) throw new Error(`invalid PromptaFlow DTO at steps[${index}].reconciliation.outcome`);
		string(decision.note, `steps[${index}].reconciliation.note`);
		string(decision.created_at, `steps[${index}].reconciliation.created_at`);
	}
	return item;
}
function decodeToolResult(name, value) {
	if ([
		"inspect_run",
		"start_run",
		"resume_run",
		"cancel_run"
	].includes(name)) return decodeRun(value);
	const item = object$1(value, name);
	if (name === "list_workflows") {
		for (const [index, workflow] of array(item.workflows, "workflows").entries()) {
			const entry = object$1(workflow, `workflows[${index}]`);
			for (const key of [
				"workflow_id",
				"name",
				"description",
				"goal_readiness"
			]) string(entry[key], `workflows[${index}].${key}`);
			number(entry.latest_version, `workflows[${index}].latest_version`);
		}
		return item;
	}
	if (name === "list_runs") {
		array(item.runs, "runs").forEach(decodeRun);
		return item;
	}
	if (name === "list_agents") {
		for (const [index, agent] of array(item.agents, "agents").entries()) {
			const entry = object$1(agent, `agents[${index}]`);
			string(entry.name, `agents[${index}].name`);
			string(entry.version, `agents[${index}].version`);
			array(entry.node_kinds, `agents[${index}].node_kinds`);
			number(entry.attempt_count, `agents[${index}].attempt_count`);
			number(entry.failed_count, `agents[${index}].failed_count`);
		}
		return item;
	}
	if (name === "generate_workflow" || name === "modify_workflow" || name === "get_authoring_job") {
		for (const key of [
			"job_id",
			"type",
			"prompt",
			"status",
			"created_at",
			"updated_at"
		]) string(item[key], `authoring_job.${key}`);
		return item;
	}
	if (name === "get_run_steps") return {
		...item,
		steps: array(item.steps, "steps").map(decodeStep)
	};
	if (name === "get_run_graph") {
		object$1(item.graph, "graph");
		return item;
	}
	if (name === "get_run_edges") {
		for (const [index, edge] of array(item.edges, "edges").entries()) {
			const entry = object$1(edge, `edges[${index}]`);
			for (const key of [
				"edge_id",
				"source_node",
				"target_node",
				"status"
			]) string(entry[key], `edges[${index}].${key}`);
		}
		return item;
	}
	if (name === "read_run_output") {
		array(item.chunks, "output.chunks");
		number(item.after, "output.after");
		boolean(item.has_more, "output.has_more");
		return item;
	}
	if (name === "list_artifacts") {
		array(item.artifacts, "artifacts").forEach((v, i) => {
			const a = object$1(v, `artifacts[${i}]`);
			string(a.artifact_id, `artifacts[${i}].artifact_id`);
			string(a.run_id, `artifacts[${i}].run_id`);
		});
		return item;
	}
	if (name === "read_artifact") {
		string(item.artifact_id, "artifact.artifact_id");
		string(item.run_id, "artifact.run_id");
		return item;
	}
	if (name === "read_artifact_content") {
		object$1(item.artifact, "artifact_content.artifact");
		if (string(item.encoding, "artifact_content.encoding") !== "base64") throw new Error("invalid PromptaFlow DTO at artifact_content.encoding");
		string(item.content, "artifact_content.content");
		return item;
	}
	if (name === "list_runtime_events") {
		array(item.events, "events");
		number(item.next_position, "next_position");
		return item;
	}
	return item;
}
//#endregion
//#region ../../integration-core/src/commands.ts
/**
* The advertised entry for a command at the revision the caller was reading,
* or undefined if there is none.
*
* Both halves matter. A command PromptaFlow never offered is a call that would fail
* at the Runtime anyway; a command offered at a *different* revision is worse,
* because it would succeed — against a Run that moved after the caller looked
* at it, doing the thing they asked to a state they never saw.
*/
function advertisedAt(run, command, expectedRevision) {
	return run.allowed_commands.find((item) => item.command === command && item.expected_version === expectedRevision);
}
/** The wire tool one command is carried by. */
function commandTool(command) {
	return command === "langgraph_run.cancel" ? "cancel_run" : "resume_run";
}
//#endregion
//#region ../../integration-core/src/gateway.ts
var PromptaFlowTransportError = class extends Error {};
const STARTUP_TIMEOUT_MS = 1e4;
const STARTUP_POLL_MS = 100;
/** Connect Harness to PromptaFlow over HTTP MCP; explicit UI entry may start it. */
/**
* How long any one MCP call may take before the transport gives up on it.
*
* Exported because a tool that deliberately blocks — `wait_authoring_request`
* parks until work arrives — has to ask for less than this. Asking for more
* does not extend the call: it aborts here, the request is cancelled at the
* Runtime, and the caller is told about a timeout it chose for itself.
*/
const PROMPTAFLOW_RPC_TIMEOUT_MS = 6e4;
var PromptaFlowGateway = class {
	command;
	commandPrefix;
	fetchImpl;
	discoveryRoot;
	hubUrl;
	runtimes = /* @__PURE__ */ new Map();
	telemetry = {
		discoveryAttempts: 0,
		rpcCalls: 0,
		transportFailures: 0
	};
	constructor(command = "paf", commandPrefix = [], fetchImpl = globalThis.fetch, discoveryRoot = process.env.PROMPTAFLOW_RUNTIME_ROOT || void 0, hubUrl = process.env.PROMPTAFLOW_HUB_URL || "http://127.0.0.1:8848") {
		this.command = command;
		this.commandPrefix = commandPrefix;
		this.fetchImpl = fetchImpl;
		this.discoveryRoot = discoveryRoot;
		this.hubUrl = hubUrl;
	}
	diagnostics() {
		return {
			...this.telemetry,
			connectedWorkspaces: this.runtimes.size
		};
	}
	async acquire(workspace, startIfMissing = false) {
		await this.runtime(workspace, startIfMissing);
		return async () => {};
	}
	/**
	* Ask the Runtime serving this Workspace to stop, and forget it.
	*
	* The Runtime's own command, not a signal: it accepts the request, answers,
	* and then exits through its host, so in-flight work is unwound rather than
	* cut. This Host is allowed to ask because the Runtime was started for it —
	* `serve` vouches for `harness:session:` actors exactly when it carries the
	* Harness tool profile, which is the profile a Gateway starts it with.
	*
	* The cached connection goes whatever the answer was. A Runtime that
	* accepted the request is on its way down, and one that refused is a
	* connection worth re-establishing rather than reusing.
	*/
	async stopRuntime(workspace, sessionId) {
		if (!/^[A-Za-z0-9:_-]{1,180}$/.test(sessionId)) throw new Error("invalid Harness session id");
		const key = await realpath(workspace.canonicalPath);
		const runtime = await this.runtimeFor(key);
		if (!runtime.baseUrl) throw new Error("this PromptaFlow Runtime published no HTTP address");
		try {
			const response = await this.fetchImpl(`${runtime.baseUrl}/api/v1/runtime/shutdown`, {
				method: "POST",
				headers: {
					"content-type": "application/json",
					"x-promptaflow-actor": `harness:session:${sessionId}`,
					"idempotency-key": crypto.randomUUID()
				},
				body: JSON.stringify({ expected_version: 0 })
			});
			if (!response.ok) {
				const detail = await response.text().catch(() => "");
				throw new Error(`PromptaFlow refused to stop: HTTP ${String(response.status)}${detail ? ` ${detail.slice(0, 200)}` : ""}`);
			}
		} finally {
			this.runtimes.delete(key);
		}
	}
	async call(workspace, sessionId, name, args) {
		if (!/^[A-Za-z0-9:_-]{1,180}$/.test(sessionId)) throw new Error("invalid Harness session id");
		const key = await realpath(workspace.canonicalPath);
		const runtime = await this.runtimeFor(key);
		const actor = `harness:session:${sessionId}`;
		let envelope;
		try {
			envelope = await this.rpc(runtime, "tools/call", {
				name,
				arguments: args,
				_meta: {
					"promptaflow/actor": actor,
					"promptaflow/workspace": {
						id: workspace.id,
						canonicalPath: key,
						...workspace.repositoryId ? { repositoryId: workspace.repositoryId } : {},
						...workspace.worktreeId ? { worktreeId: workspace.worktreeId } : {},
						...workspace.baseRevision ? { baseRevision: workspace.baseRevision } : {},
						...workspace.isolationMode ? { isolationMode: workspace.isolationMode } : {}
					}
				}
			});
		} catch (error) {
			if (error instanceof PromptaFlowTransportError) {
				this.telemetry.transportFailures++;
				this.telemetry.lastTransportError = error.message;
				this.runtimes.delete(key);
			}
			throw error;
		}
		if (envelope.isError) throw new Error(JSON.stringify(envelope.structuredContent ?? envelope.content));
		return decodeToolResult(name, envelope.structuredContent);
	}
	/** Stable Hub UI namespace for this Workspace. */
	async uiUrl(workspace) {
		return (await this.runtime(workspace)).uiUrl;
	}
	async authoringOutput(workspace, sessionId, outputHref, after) {
		if (!/^\/api\/v1\/workflow-authoring-jobs\/[^/?#]+\/output$/u.test(outputHref)) throw new Error("PromptaFlow returned an invalid authoring output address");
		if (!Number.isSafeInteger(after) || after < 0) throw new Error("invalid authoring output cursor");
		const runtime = await this.runtime(workspace);
		if (!runtime.baseUrl) throw new Error("PromptaFlow Runtime did not publish a browser address");
		const response = await this.fetchImpl(`${runtime.baseUrl.replace(/\/$/, "")}${outputHref}?after=${String(after)}`, { headers: { "x-promptaflow-actor": `harness:session:${sessionId}` } });
		if (!response.ok) throw new PromptaFlowTransportError(`PromptaFlow authoring output failed with HTTP ${String(response.status)}`);
		const envelope = await response.json();
		if (!envelope.data || !Array.isArray(envelope.data.chunks)) throw new Error("PromptaFlow authoring output returned invalid JSON");
		return envelope.data;
	}
	async run(workspace, sessionId, runId) {
		return decodeRun(await this.call(workspace, sessionId, "inspect_run", { run_id: runId }));
	}
	/** Generate a Workflow and execute its Goal through Runtime MCP, without a UI.
	*
	* The authoring and execution calls are deliberately kept in one method so a
	* host can offer one synchronous operation. Runtime remains authoritative:
	* the job's published workflow id is used verbatim, and every mutation gets
	* its own idempotency key. No page routes or guessed URLs are involved.
	*/
	async generateAndRunGoal(workspace, sessionId, prompt, goal, input = {}, options = {}) {
		const generated = await this.call(workspace, sessionId, "generate_workflow", {
			prompt,
			idempotency_key: randomUUID(),
			...options.agent === void 0 ? {} : { agent: options.agent },
			...options.displayLanguage === void 0 ? {} : { display_language: options.displayLanguage }
		});
		const workflow = await this.waitForAuthoringJob(workspace, sessionId, generated.job_id, options);
		if (workflow.status !== "done") throw new Error(`PromptaFlow workflow generation ${workflow.status}: ${workflow.error?.message ?? workflow.job_id}`);
		if (typeof workflow.workflow_id !== "string" || !workflow.workflow_id) throw new Error("PromptaFlow completed workflow generation without a workflow_id");
		const started = await this.call(workspace, sessionId, "start_run", {
			workflow_id: workflow.workflow_id,
			goal,
			input,
			wait: false,
			idempotency_key: randomUUID()
		});
		return {
			workflow,
			run: await this.waitForRun(workspace, sessionId, started.run_id, options)
		};
	}
	async waitForAuthoringJob(workspace, sessionId, jobId, options) {
		const pollMs = options.pollMs ?? 500;
		const deadline = Date.now() + (options.timeoutMs ?? 6e5);
		while (true) {
			const job = await this.call(workspace, sessionId, "get_authoring_job", { job_id: jobId });
			if (job.status === "done" || job.status === "failed" || job.status === "cancelled") return job;
			if (Date.now() >= deadline) throw new Error(`PromptaFlow workflow generation timed out: ${jobId}`);
			await new Promise((resolve) => setTimeout(resolve, pollMs));
		}
	}
	async waitForRun(workspace, sessionId, runId, options) {
		const pollMs = options.pollMs ?? 500;
		const deadline = Date.now() + (options.timeoutMs ?? 6e5);
		while (true) {
			const run = await this.run(workspace, sessionId, runId);
			if ([
				"completed",
				"failed",
				"cancelled",
				"unknown"
			].includes(run.status)) return run;
			if (Date.now() >= deadline) throw new Error(`PromptaFlow Goal execution timed out: ${runId}`);
			await new Promise((resolve) => setTimeout(resolve, pollMs));
		}
	}
	async runtime(workspace, startIfMissing = false) {
		return await this.runtimeFor(await realpath(workspace.canonicalPath), startIfMissing);
	}
	async runtimeFor(key, startIfMissing = false) {
		let promise = this.runtimes.get(key);
		if (promise === void 0) {
			promise = this.connect(key, startIfMissing);
			this.runtimes.set(key, promise);
			promise.catch(() => this.runtimes.delete(key));
		}
		return await promise;
	}
	async connect(workspaceRoot, startIfMissing) {
		const workspaceId = await this.registerWorkspace(workspaceRoot);
		const hub = this.hubUrl.replace(/\/$/, "");
		const mcpUrl = `${hub}/workspaces/${workspaceId}/mcp`;
		const deadline = Date.now() + STARTUP_TIMEOUT_MS;
		let started = false;
		while (true) {
			const runtime = {
				mcpUrl,
				baseUrl: (await this.discover(workspaceRoot))?.base_url ?? "",
				uiUrl: `${hub}/workspaces/${workspaceId}/ui/`,
				nextId: 1,
				capabilities: {}
			};
			try {
				await this.rpc(runtime, "initialize", {
					protocolVersion: "2025-06-18",
					capabilities: {},
					clientInfo: {
						name: "dsh-promptaflow",
						version: "0.6.2-alpha"
					}
				});
				runtime.capabilities = await this.callRaw(runtime, "get_capabilities", {});
				if (runtime.capabilities.integration_protocol !== "promptaflow-harness/2") throw new Error("incompatible PromptaFlow integration protocol");
				this.telemetry.lastConnectedAt = (/* @__PURE__ */ new Date()).toISOString();
				this.telemetry.lastTransportError = void 0;
				runtime.baseUrl = (await this.discover(workspaceRoot))?.base_url ?? runtime.baseUrl;
				return runtime;
			} catch (error) {
				if (!startIfMissing || !(error instanceof PromptaFlowTransportError) || Date.now() >= deadline) throw error;
				if (!started) {
					await this.startHub();
					started = true;
				}
				await new Promise((resolve) => setTimeout(resolve, STARTUP_POLL_MS));
			}
		}
	}
	async registerWorkspace(workspaceRoot) {
		const output = await this.runPromptaFlow([
			"hub",
			"register",
			workspaceRoot
		], workspaceRoot);
		try {
			const value = JSON.parse(output);
			if (typeof value.workspace_id === "string" && value.workspace_id) return value.workspace_id;
		} catch {}
		throw new Error("PromptaFlow Hub workspace registration returned invalid JSON");
	}
	async runPromptaFlow(args, cwd) {
		return await new Promise((resolve, reject) => {
			const child = spawn(this.command, [...this.commandPrefix, ...args], {
				cwd,
				stdio: [
					"ignore",
					"pipe",
					"pipe"
				]
			});
			let stdout = "", stderr = "";
			child.stdout.setEncoding("utf8");
			child.stdout.on("data", (chunk) => {
				stdout += chunk;
			});
			child.stderr.setEncoding("utf8");
			child.stderr.on("data", (chunk) => {
				stderr += chunk;
			});
			child.once("error", reject);
			child.once("exit", (code) => code === 0 ? resolve(stdout) : reject(/* @__PURE__ */ new Error(`PromptaFlow command failed: ${args.join(" ")} (code ${String(code)})${stderr ? `: ${stderr.trim()}` : ""}`)));
		});
	}
	async startHub() {
		const url = new URL(this.hubUrl);
		if (url.protocol !== "http:" || ![
			"127.0.0.1",
			"localhost",
			"::1"
		].includes(url.hostname)) throw new Error(`PromptaFlow Hub auto-start requires a loopback HTTP URL: ${this.hubUrl}`);
		const port = url.port ? Number(url.port) : 80;
		const log = await open(join(tmpdir(), `dsh-promptaflow-hub-${String(port)}.log`), "w");
		try {
			const child = spawn(this.command, [
				...this.commandPrefix,
				"hub",
				"serve",
				"--host",
				url.hostname,
				"--port",
				String(port)
			], {
				detached: true,
				stdio: [
					"ignore",
					log.fd,
					log.fd
				]
			});
			await new Promise((resolve, reject) => {
				child.once("spawn", resolve);
				child.once("error", reject);
			});
			child.unref();
		} finally {
			await log.close();
		}
	}
	async discover(workspaceRoot) {
		this.telemetry.discoveryAttempts++;
		const output = await new Promise((resolve, reject) => {
			const child = spawn(this.command, [
				...this.commandPrefix,
				"runtimes",
				"--json",
				...this.discoveryRoot ? ["--root", this.discoveryRoot] : []
			], {
				cwd: workspaceRoot,
				stdio: [
					"ignore",
					"pipe",
					"pipe"
				]
			});
			let stdout = "", stderr = "";
			child.stdout.setEncoding("utf8");
			child.stdout.on("data", (chunk) => {
				stdout += chunk;
			});
			child.stderr.setEncoding("utf8");
			child.stderr.on("data", (chunk) => {
				stderr += chunk;
			});
			child.once("error", reject);
			child.once("exit", (code) => code === 0 ? resolve(stdout) : reject(/* @__PURE__ */ new Error(`PromptaFlow Runtime discovery failed with code ${String(code)}${stderr ? `: ${stderr.trim()}` : ""}`)));
		});
		let entries;
		try {
			entries = JSON.parse(output);
		} catch {
			throw new Error("PromptaFlow Runtime discovery returned invalid JSON");
		}
		if (!Array.isArray(entries)) throw new Error("PromptaFlow Runtime discovery must return an array");
		const matches = entries.filter((entry) => entry.project_root === workspaceRoot && entry.base_url);
		if (matches.length === 0) return void 0;
		if (matches.length > 1) throw new Error(`Multiple PromptaFlow Runtimes claim Workspace ${workspaceRoot}`);
		return matches[0];
	}
	async rpc(runtime, method, params) {
		this.telemetry.rpcCalls++;
		const id = runtime.nextId++;
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), PROMPTAFLOW_RPC_TIMEOUT_MS);
		try {
			const actor = this.actorFrom(params);
			const response = await this.fetchImpl(runtime.mcpUrl, {
				method: "POST",
				headers: {
					"content-type": "application/json",
					...actor ? { "x-promptaflow-actor": actor } : {}
				},
				signal: controller.signal,
				body: JSON.stringify({
					jsonrpc: "2.0",
					id,
					method,
					params
				})
			});
			if (!response.ok) throw new PromptaFlowTransportError(`PromptaFlow MCP HTTP ${String(response.status)}`);
			const message = await response.json();
			if (message.error !== void 0) throw new Error(message.error.message || "PromptaFlow MCP request failed");
			return message.result;
		} catch (error) {
			if (controller.signal.aborted) throw new PromptaFlowTransportError(`PromptaFlow MCP ${method} timed out`);
			if (error instanceof TypeError) throw new PromptaFlowTransportError(`PromptaFlow MCP transport failed: ${error.message}`);
			throw error;
		} finally {
			clearTimeout(timer);
		}
	}
	actorFrom(params) {
		const actor = params._meta?.["promptaflow/actor"];
		return typeof actor === "string" ? actor : void 0;
	}
	async callRaw(runtime, name, args) {
		return (await this.rpc(runtime, "tools/call", {
			name,
			arguments: args
		})).structuredContent;
	}
};
//#endregion
//#region ../../integration-core/src/run-progress.ts
/** Run statuses there is no coming back from. */
const TERMINAL$1 = /* @__PURE__ */ new Set([
	"completed",
	"failed",
	"cancelled",
	"unknown"
]);
/** Whether a Run could still do something. */
function isLive(status) {
	return !TERMINAL$1.has(status);
}
/**
* The Runs the Goal page shows: everything still moving, or the one that
* moved last when nothing is.
*
* A Goal reaching its end is the moment its result matters most, and dropping
* it from the page right then answered "what happened" with an empty page —
* the reader watched four steps go green and was left looking at "nothing is
* running here". So a finished Goal stays, with its steps and its outcome,
* until the next one starts and takes the page.
*
* Shared because the Host reads steps for exactly the Runs this page draws. A
* Host that kept its own idea of that would go on serving a settled Run's last
* *running* step forever, since the step read stops with the Run.
*/
function goalRuns(rows) {
	const live = rows.filter((row) => row.live);
	if (live.length) return live;
	const latest = rows.reduce((best, row) => best === void 0 || row.updatedAt > best.updatedAt ? row : best, void 0);
	return latest === void 0 ? [] : [latest];
}
//#endregion
//#region ../../integration-core/src/session-bridge.ts
function sessionCanBridge(header) {
	return Boolean(header.cwd) && (header.delegationDepth ?? 0) === 0;
}
const TERMINAL = /* @__PURE__ */ new Set([
	"completed",
	"failed",
	"cancelled",
	"unknown"
]);
var PromptaFlowSessionBridge = class {
	gateway;
	cursor;
	intervalMs;
	constructor(gateway, cursor, intervalMs = 500) {
		this.gateway = gateway;
		this.cursor = cursor;
		this.intervalMs = intervalMs;
	}
	async run(workspace, sessionId, sink, signal, knownRuns = []) {
		const release = await this.gateway.acquire(workspace);
		try {
			const known = new Set(knownRuns);
			let position = await this.cursor.load(workspace.id, sessionId);
			while (!signal.aborted) {
				const page = await this.gateway.call(workspace, sessionId, "list_runtime_events", {
					...position === void 0 ? {} : { after_position: position },
					limit: 200
				});
				const latest = /* @__PURE__ */ new Map();
				for (const event of page.events) latest.set(event.run_id, Math.max(latest.get(event.run_id) ?? 0, event.position));
				for (const [runId, sourcePosition] of latest) {
					const run = await this.gateway.run(workspace, sessionId, runId);
					const steps = await this.gateway.call(workspace, sessionId, "get_run_steps", { run_id: runId });
					if (!known.has(runId)) {
						await sink.append({
							type: "promptaflow/run-started",
							sourcePosition,
							runId,
							workspaceId: workspace.id,
							goal: run.goal,
							workflowId: run.workflow_id,
							workflowVersion: run.workflow_version,
							revision: run.revision,
							status: run.status,
							createdAt: run.created_at
						});
						known.add(runId);
					}
					const counts = {};
					for (const step of steps.steps) counts[step.status] = (counts[step.status] ?? 0) + 1;
					if (TERMINAL.has(run.status)) {
						await sink.append({
							type: "promptaflow/run-ended",
							sourcePosition,
							runId,
							revision: run.revision,
							status: run.status,
							artifactCount: run.artifact_count,
							updatedAt: run.updated_at
						});
						known.add(runId);
					} else await sink.append({
						type: "promptaflow/run-checkpoint",
						sourcePosition,
						runId,
						revision: run.revision,
						status: run.status,
						currentSteps: steps.steps,
						stepCounts: counts,
						artifactCount: run.artifact_count,
						updatedAt: run.updated_at
					});
				}
				position = page.next_position;
				await this.cursor.save(workspace.id, sessionId, position);
				if (page.events.length === 0) await new Promise((resolve) => {
					const timer = setTimeout(resolve, this.intervalMs);
					signal.addEventListener("abort", () => {
						clearTimeout(timer);
						resolve();
					}, { once: true });
				});
			}
		} finally {
			await release();
		}
	}
};
/** One line per Workflow: what to name it, and what it needs. */
function line(workflow) {
	const inputs = Array.isArray(workflow.inputs) ? workflow.inputs.map((input) => input.id).filter((id) => typeof id === "string") : [];
	const needs = inputs.length ? ` (input: ${inputs.join(", ")})` : "";
	const name = workflow.name || workflow.workflow_id;
	return `- ${workflow.workflow_id}@${String(workflow.latest_version)} — ${name}${needs}`;
}
var WorkflowCatalog = class {
	now;
	byWorkspace = /* @__PURE__ */ new Map();
	constructor(now = Date.now) {
		this.now = now;
	}
	remember(canonicalPath, workflows) {
		this.byWorkspace.set(canonicalPath, {
			workflows,
			at: this.now()
		});
	}
	forget(canonicalPath) {
		this.byWorkspace.delete(canonicalPath);
	}
	/**
	* Everything remembered for one Workspace, in the order it was read.
	*
	* All of it, not the runnable subset: this answers the panel, where a person
	* is reading a catalog and a Workflow that has gone unrunnable is something
	* they need to see — it is the one they have to go and fix. `render`, which
	* answers the model, keeps the filter: there a name is an offer to run.
	*/
	list(canonicalPath) {
		return this.byWorkspace.get(canonicalPath)?.workflows ?? [];
	}
	/**
	* The entry for a workspace while it is still worth speaking for.
	*
	* The TTL is stated here and nowhere else. `stale` and `render` are the two
	* questions asked about it — "should this be re-read" and "may this be put
	* in front of the model" — and they were each spelling the comparison out,
	* which is two places to edit and one poll doing the arithmetic twice.
	*/
	fresh(canonicalPath) {
		const entry = this.byWorkspace.get(canonicalPath);
		if (entry === void 0 || this.now() - entry.at > 3e5) return void 0;
		return entry;
	}
	/** Whether a workspace's entry is missing or old enough to re-read. */
	stale(canonicalPath) {
		return this.fresh(canonicalPath) === void 0;
	}
	/**
	* The prompt contribution, or an empty string when there is nothing to say.
	*
	* Empty rather than a sentence explaining the emptiness: a contribution that
	* says "no Workflows are known" costs the same tokens every turn and tells
	* the model nothing it could not infer from the absence.
	*/
	render(canonicalPath) {
		const entry = this.fresh(canonicalPath);
		if (entry === void 0) return "";
		const ready = entry.workflows.filter((item) => item.goal_readiness === "ready");
		if (!ready.length) return "";
		const shown = ready.slice(0, 20).map(line);
		const omitted = ready.length - shown.length;
		return [
			`PromptaFlow Workflows ready in ${canonicalPath}:`,
			...shown,
			...omitted > 0 ? [`- …and ${String(omitted)} more; call promptaflow_list_workflows for the rest.`] : [],
			"Start one with promptaflow_start_run. Progress appears in the PromptaFlow panel."
		].join("\n");
	}
};
//#endregion
//#region src/promptaflow-tools.ts
const JSON_OUTPUT = {
	schema: {},
	render: (_args, value) => [{
		type: "text",
		text: JSON.stringify(value, null, 2)
	}]
};
const object = (properties, required = []) => ({
	type: "object",
	properties,
	...required.length ? { required } : {},
	additionalProperties: false
});
function args(value) {
	if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("PromptaFlow tool arguments must be an object");
	return value;
}
var PromptaFlowToolBridge = class {
	ctx;
	gateway;
	watch;
	tools;
	registry;
	constructor(ctx, gateway, watch = () => {}) {
		this.ctx = ctx;
		this.gateway = gateway;
		this.watch = watch;
		this.tools = ctx.get("tools");
		this.registry = ctx.get("workspaceRegistry");
	}
	register() {
		for (const definition of this.definitions()) this.tools.register(definition);
	}
	definitions() {
		return [
			this.definition("promptaflow_list_workflows", "List published PromptaFlow workflows available in this Session Workspace.", object({ ready_only: { type: "boolean" } }), "list_workflows", true),
			this.definition("promptaflow_list_runs", "List PromptaFlow workflow runs owned by this Harness Session.", object({
				status: { type: "string" },
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200
				}
			}), "list_runs", true),
			this.definition("promptaflow_list_delegations", "Check once on the first turn of this Session for resumable PromptaFlow Agent work. Stay silent when the returned list is empty.", object({
				statuses: {
					type: "array",
					items: { type: "string" },
					maxItems: 6
				},
				limit: {
					type: "integer",
					minimum: 1,
					maximum: 200
				}
			}), "list_delegations", true),
			{
				name: "promptaflow_claim_delegation",
				description: "Claim the next queued PromptaFlow Agent step for this Harness Session.",
				parameters: object({ lease_seconds: {
					type: "integer",
					minimum: 5,
					maximum: 300
				} }),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value), { workspace, session } = await this.route(exec);
					return await this.gateway.call(workspace, String(session.id), "claim_delegation", {
						worker_id: `harness-session:${String(session.id)}`,
						...input.lease_seconds === void 0 ? {} : { lease_seconds: input.lease_seconds }
					});
				}
			},
			{
				name: "promptaflow_renew_delegation",
				description: "Renew an PromptaFlow Agent-step lease held by this Harness Session.",
				parameters: object({
					delegation_id: { type: "string" },
					lease_seconds: {
						type: "integer",
						minimum: 5,
						maximum: 300
					}
				}, ["delegation_id"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value), { workspace, session } = await this.route(exec);
					return await this.gateway.call(workspace, String(session.id), "renew_delegation", {
						delegation_id: input.delegation_id,
						worker_id: `harness-session:${String(session.id)}`,
						...input.lease_seconds === void 0 ? {} : { lease_seconds: input.lease_seconds }
					});
				}
			},
			{
				name: "promptaflow_complete_delegation",
				description: "Return exactly one result object or error for an PromptaFlow Agent step.",
				parameters: object({
					delegation_id: { type: "string" },
					result: { type: "object" },
					error: { type: "string" }
				}, ["delegation_id"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value), { workspace, session } = await this.route(exec);
					return await this.gateway.call(workspace, String(session.id), "complete_delegation", {
						...input,
						worker_id: `harness-session:${String(session.id)}`
					});
				}
			},
			this.definition("promptaflow_reconcile_delegation", "Submit a user-verified outcome for unknown PromptaFlow Agent work; never execute unknown work again.", object({
				delegation_id: { type: "string" },
				outcome: {
					type: "string",
					enum: ["confirmed_succeeded", "confirmed_failed"]
				},
				note: { type: "string" },
				result: { type: "object" },
				error: { type: "string" },
				idempotency_key: { type: "string" }
			}, [
				"delegation_id",
				"outcome",
				"idempotency_key"
			]), "reconcile_delegation", false),
			this.definition("promptaflow_inspect_run", "Inspect one PromptaFlow Run, including status, revision, interrupts and allowed commands.", object({ run_id: { type: "string" } }, ["run_id"]), "inspect_run", true),
			{
				name: "promptaflow_start_run",
				description: "Start a published PromptaFlow workflow in the current Workspace. Returns immediately so progress appears in the PromptaFlow Run Card.",
				parameters: object({
					workflow_id: { type: "string" },
					workflow_version: { type: "integer" },
					input: { type: "object" },
					goal: {
						type: "string",
						maxLength: 4e3
					}
				}, ["workflow_id"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value);
					return await this.call(exec, "start_run", {
						...input,
						wait: false,
						idempotency_key: crypto.randomUUID()
					});
				}
			},
			{
				name: "promptaflow_generate_workflow",
				description: "Draft a new PromptaFlow workflow from a description and publish it if the compiler accepts it. Returns a job immediately — authoring takes a while — so poll promptaflow_get_authoring_job with the job_id until its status leaves queued/running. Nothing is published until the compiler accepts the draft, so a failed job has changed nothing. Progress also appears in the PromptaFlow panel.",
				parameters: object({
					prompt: {
						type: "string",
						maxLength: 4e3
					},
					agent: {
						type: "string",
						description: "Which Agent writes it; the Runtime picks one if omitted."
					}
				}, ["prompt"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value);
					const { workspace, session } = await this.route(exec);
					const job = await this.gateway.call(workspace, String(session.id), "generate_workflow", {
						prompt: String(input.prompt),
						...input.agent === void 0 ? {} : { agent: String(input.agent) },
						idempotency_key: crypto.randomUUID()
					});
					this.watch(workspace, String(session.id), job);
					return job;
				}
			},
			this.definition("promptaflow_get_authoring_job", "Check an PromptaFlow authoring job started by promptaflow_generate_workflow. Status queued or running means it is still going; done carries the published workflow, failed carries why.", object({ job_id: { type: "string" } }, ["job_id"]), "get_authoring_job", true),
			{
				name: "promptaflow_cancel_run",
				description: "Cancel an PromptaFlow Run if its latest server-advertised commands allow cancellation.",
				parameters: object({ run_id: { type: "string" } }, ["run_id"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const runId = String(args(value).run_id);
					return await this.command(exec, runId, "langgraph_run.cancel");
				}
			},
			{
				name: "promptaflow_resume_run",
				description: "Resume an interrupted PromptaFlow Run using its latest server-advertised revision.",
				parameters: object({
					run_id: { type: "string" },
					value: {},
					interrupt_id: { type: "string" }
				}, ["run_id"]),
				output: JSON_OUTPUT,
				timeoutMs: 6e4,
				execute: async (value, exec) => {
					const input = args(value), runId = String(input.run_id);
					return await this.command(exec, runId, "langgraph_run.resume", input.value, input.interrupt_id);
				}
			}
		];
	}
	definition(name, description, parameters, wireName, concurrencySafe) {
		return {
			name,
			description,
			parameters,
			output: JSON_OUTPUT,
			timeoutMs: 6e4,
			isConcurrencySafe: concurrencySafe ? () => true : void 0,
			execute: async (value, exec) => await this.call(exec, wireName, args(value))
		};
	}
	async command(exec, runId, command, value, interruptId) {
		const { workspace, session } = await this.route(exec);
		const advertised = (await this.gateway.run(workspace, String(session.id), runId)).allowed_commands.find((item) => item.command === command);
		if (!advertised) throw new Error(`PromptaFlow no longer advertises ${command} for Run ${runId}`);
		return await this.gateway.call(workspace, String(session.id), command === "langgraph_run.cancel" ? "cancel_run" : "resume_run", {
			run_id: runId,
			expected_version: advertised.expected_version,
			idempotency_key: crypto.randomUUID(),
			...value === void 0 ? {} : { value },
			...interruptId === void 0 ? {} : { interrupt_id: interruptId }
		});
	}
	async call(exec, name, input) {
		const { workspace, session } = await this.route(exec);
		return await this.gateway.call(workspace, String(session.id), name, input);
	}
	async route(exec) {
		const session = exec.agent?.session;
		if (!session) throw new Error("PromptaFlow tools require a live Harness Agent Session");
		const cwd = session.header.cwd;
		if (!cwd) throw new Error("PromptaFlow tools require the Session to have a Workspace cwd");
		const registered = await this.registry.resolveByPath(cwd);
		return {
			session,
			workspace: {
				id: registered ? String(registered.id) : `cwd:${cwd}`,
				canonicalPath: registered?.path ?? cwd
			}
		};
	}
};
//#endregion
//#region src/artifact-import.ts
const IMAGE_TYPES = /* @__PURE__ */ new Set([
	"image/png",
	"image/jpeg",
	"image/webp",
	"image/gif"
]);
function artifactImageInput(content) {
	const mediaType = content.artifact.content_type;
	if (!mediaType || !IMAGE_TYPES.has(mediaType)) throw new Error(`Harness Attachment import supports images only; Artifact is ${mediaType || "unknown"}`);
	if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(content.content)) throw new Error("PromptaFlow Artifact content is not canonical base64");
	return {
		data: Uint8Array.from(Buffer.from(content.content, "base64")),
		mediaType,
		name: String(content.artifact.name || content.artifact.filename || content.artifact.artifact_id)
	};
}
//#endregion
//#region src/index.ts
/** How long to let one authoring turn run before giving the request back.
*  Under the broker's own lease, so this Host stops waiting before PromptaFlow
*  stops expecting it to. */
const AUTHORING_TURN_MS = 24e4;
/** How long a settled job stays on the panel before it stops being news. */
const AUTHORING_LINGER_MS = 6e4;
/**
* How many Runs the panel poll will read steps for.
*
* Steps are one extra Runtime read per Run, on a two-second poll, so this is
* not free the way the Run list is — the list is one read whatever its length.
* A Workspace with more than a handful of Runs moving at once has a different
* problem than a missing progress line, and the ones past the cap are the ones
* furthest down a list ordered by recency.
*/
const LIVE_STEP_LIMIT = 6;
var PromptaFlowRemoteService = (() => {
	let _classSuper = TypertRemoteService;
	let _instanceExtraInitializers = [];
	let _getAuthoringOutput_decorators;
	let _getRuntime_decorators;
	let _getRuntimeUi_decorators;
	let _getPanelState_decorators;
	let _getRunDetail_decorators;
	let _getWorkflowDefinition_decorators;
	let _getStepOutput_decorators;
	let _runCommand_decorators;
	let _reconcileStep_decorators;
	let _stopRuntime_decorators;
	let _getDiagnostics_decorators;
	let _listWorkflows_decorators;
	let _listRuns_decorators;
	let _generateWorkflow_decorators;
	let _modifyWorkflow_decorators;
	let _getAuthoringJob_decorators;
	let _getRun_decorators;
	let _getSteps_decorators;
	let _getGraph_decorators;
	let _getEdges_decorators;
	let _readOutput_decorators;
	let _listArtifacts_decorators;
	let _getArtifact_decorators;
	let _getArtifactContent_decorators;
	let _readArtifactText_decorators;
	let _exportArtifact_decorators;
	let _importArtifact_decorators;
	let _reconcileDelegation_decorators;
	let _executeCommand_decorators;
	return class extends _classSuper {
		static {
			__setFunctionName(this, "PromptaFlowRemoteService");
		}
		static {
			const _metadata = typeof Symbol === "function" && Symbol.metadata ? Object.create(_classSuper[Symbol.metadata] ?? null) : void 0;
			_getAuthoringOutput_decorators = [Remote("getAuthoringOutput")];
			_getRuntime_decorators = [Remote("getRuntime")];
			_getRuntimeUi_decorators = [Remote("getRuntimeUi")];
			_getPanelState_decorators = [Remote("getPanelState")];
			_getRunDetail_decorators = [Remote("getRunDetail")];
			_getWorkflowDefinition_decorators = [Remote("getWorkflowDefinition")];
			_getStepOutput_decorators = [Remote("getStepOutput")];
			_runCommand_decorators = [Remote("runCommand")];
			_reconcileStep_decorators = [Remote("reconcileStep")];
			_stopRuntime_decorators = [Remote("stopRuntime")];
			_getDiagnostics_decorators = [Remote("getDiagnostics")];
			_listWorkflows_decorators = [Remote("listWorkflows")];
			_listRuns_decorators = [Remote("listRuns")];
			_generateWorkflow_decorators = [Remote("generateWorkflow")];
			_modifyWorkflow_decorators = [Remote("modifyWorkflow")];
			_getAuthoringJob_decorators = [Remote("getAuthoringJob")];
			_getRun_decorators = [Remote("getRun")];
			_getSteps_decorators = [Remote("getSteps")];
			_getGraph_decorators = [Remote("getGraph")];
			_getEdges_decorators = [Remote("getEdges")];
			_readOutput_decorators = [Remote("readOutput")];
			_listArtifacts_decorators = [Remote("listArtifacts")];
			_getArtifact_decorators = [Remote("getArtifact")];
			_getArtifactContent_decorators = [Remote("getArtifactContent")];
			_readArtifactText_decorators = [Remote("readArtifactText")];
			_exportArtifact_decorators = [Remote("exportArtifact")];
			_importArtifact_decorators = [Remote("importArtifact")];
			_reconcileDelegation_decorators = [Remote("reconcileDelegation")];
			_executeCommand_decorators = [Remote("executeCommand")];
			__esDecorate(this, null, _getAuthoringOutput_decorators, {
				kind: "method",
				name: "getAuthoringOutput",
				static: false,
				private: false,
				access: {
					has: (obj) => "getAuthoringOutput" in obj,
					get: (obj) => obj.getAuthoringOutput
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getRuntime_decorators, {
				kind: "method",
				name: "getRuntime",
				static: false,
				private: false,
				access: {
					has: (obj) => "getRuntime" in obj,
					get: (obj) => obj.getRuntime
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getRuntimeUi_decorators, {
				kind: "method",
				name: "getRuntimeUi",
				static: false,
				private: false,
				access: {
					has: (obj) => "getRuntimeUi" in obj,
					get: (obj) => obj.getRuntimeUi
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getPanelState_decorators, {
				kind: "method",
				name: "getPanelState",
				static: false,
				private: false,
				access: {
					has: (obj) => "getPanelState" in obj,
					get: (obj) => obj.getPanelState
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getRunDetail_decorators, {
				kind: "method",
				name: "getRunDetail",
				static: false,
				private: false,
				access: {
					has: (obj) => "getRunDetail" in obj,
					get: (obj) => obj.getRunDetail
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getWorkflowDefinition_decorators, {
				kind: "method",
				name: "getWorkflowDefinition",
				static: false,
				private: false,
				access: {
					has: (obj) => "getWorkflowDefinition" in obj,
					get: (obj) => obj.getWorkflowDefinition
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getStepOutput_decorators, {
				kind: "method",
				name: "getStepOutput",
				static: false,
				private: false,
				access: {
					has: (obj) => "getStepOutput" in obj,
					get: (obj) => obj.getStepOutput
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _runCommand_decorators, {
				kind: "method",
				name: "runCommand",
				static: false,
				private: false,
				access: {
					has: (obj) => "runCommand" in obj,
					get: (obj) => obj.runCommand
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _reconcileStep_decorators, {
				kind: "method",
				name: "reconcileStep",
				static: false,
				private: false,
				access: {
					has: (obj) => "reconcileStep" in obj,
					get: (obj) => obj.reconcileStep
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _stopRuntime_decorators, {
				kind: "method",
				name: "stopRuntime",
				static: false,
				private: false,
				access: {
					has: (obj) => "stopRuntime" in obj,
					get: (obj) => obj.stopRuntime
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getDiagnostics_decorators, {
				kind: "method",
				name: "getDiagnostics",
				static: false,
				private: false,
				access: {
					has: (obj) => "getDiagnostics" in obj,
					get: (obj) => obj.getDiagnostics
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _listWorkflows_decorators, {
				kind: "method",
				name: "listWorkflows",
				static: false,
				private: false,
				access: {
					has: (obj) => "listWorkflows" in obj,
					get: (obj) => obj.listWorkflows
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _listRuns_decorators, {
				kind: "method",
				name: "listRuns",
				static: false,
				private: false,
				access: {
					has: (obj) => "listRuns" in obj,
					get: (obj) => obj.listRuns
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _generateWorkflow_decorators, {
				kind: "method",
				name: "generateWorkflow",
				static: false,
				private: false,
				access: {
					has: (obj) => "generateWorkflow" in obj,
					get: (obj) => obj.generateWorkflow
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _modifyWorkflow_decorators, {
				kind: "method",
				name: "modifyWorkflow",
				static: false,
				private: false,
				access: {
					has: (obj) => "modifyWorkflow" in obj,
					get: (obj) => obj.modifyWorkflow
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getAuthoringJob_decorators, {
				kind: "method",
				name: "getAuthoringJob",
				static: false,
				private: false,
				access: {
					has: (obj) => "getAuthoringJob" in obj,
					get: (obj) => obj.getAuthoringJob
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getRun_decorators, {
				kind: "method",
				name: "getRun",
				static: false,
				private: false,
				access: {
					has: (obj) => "getRun" in obj,
					get: (obj) => obj.getRun
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getSteps_decorators, {
				kind: "method",
				name: "getSteps",
				static: false,
				private: false,
				access: {
					has: (obj) => "getSteps" in obj,
					get: (obj) => obj.getSteps
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getGraph_decorators, {
				kind: "method",
				name: "getGraph",
				static: false,
				private: false,
				access: {
					has: (obj) => "getGraph" in obj,
					get: (obj) => obj.getGraph
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getEdges_decorators, {
				kind: "method",
				name: "getEdges",
				static: false,
				private: false,
				access: {
					has: (obj) => "getEdges" in obj,
					get: (obj) => obj.getEdges
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _readOutput_decorators, {
				kind: "method",
				name: "readOutput",
				static: false,
				private: false,
				access: {
					has: (obj) => "readOutput" in obj,
					get: (obj) => obj.readOutput
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _listArtifacts_decorators, {
				kind: "method",
				name: "listArtifacts",
				static: false,
				private: false,
				access: {
					has: (obj) => "listArtifacts" in obj,
					get: (obj) => obj.listArtifacts
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getArtifact_decorators, {
				kind: "method",
				name: "getArtifact",
				static: false,
				private: false,
				access: {
					has: (obj) => "getArtifact" in obj,
					get: (obj) => obj.getArtifact
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _getArtifactContent_decorators, {
				kind: "method",
				name: "getArtifactContent",
				static: false,
				private: false,
				access: {
					has: (obj) => "getArtifactContent" in obj,
					get: (obj) => obj.getArtifactContent
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _readArtifactText_decorators, {
				kind: "method",
				name: "readArtifactText",
				static: false,
				private: false,
				access: {
					has: (obj) => "readArtifactText" in obj,
					get: (obj) => obj.readArtifactText
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _exportArtifact_decorators, {
				kind: "method",
				name: "exportArtifact",
				static: false,
				private: false,
				access: {
					has: (obj) => "exportArtifact" in obj,
					get: (obj) => obj.exportArtifact
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _importArtifact_decorators, {
				kind: "method",
				name: "importArtifact",
				static: false,
				private: false,
				access: {
					has: (obj) => "importArtifact" in obj,
					get: (obj) => obj.importArtifact
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _reconcileDelegation_decorators, {
				kind: "method",
				name: "reconcileDelegation",
				static: false,
				private: false,
				access: {
					has: (obj) => "reconcileDelegation" in obj,
					get: (obj) => obj.reconcileDelegation
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			__esDecorate(this, null, _executeCommand_decorators, {
				kind: "method",
				name: "executeCommand",
				static: false,
				private: false,
				access: {
					has: (obj) => "executeCommand" in obj,
					get: (obj) => obj.executeCommand
				},
				metadata: _metadata
			}, null, _instanceExtraInitializers);
			if (_metadata) Object.defineProperty(this, Symbol.metadata, {
				enumerable: true,
				configurable: true,
				writable: true,
				value: _metadata
			});
		}
		static inject = [
			"sessions",
			"workspaceRegistry",
			"tools",
			"attachments",
			"systemPrompt",
			"agents"
		];
		gateway = (__runInitializers(this, _instanceExtraInitializers), new PromptaFlowGateway());
		agents;
		catalog = new WorkflowCatalog();
		/** Authoring jobs started from this Harness, per Workspace.
		*
		*  Held here because there is nothing to ask: a job is addressed by an id
		*  the starter was handed, and `get_authoring_job` is scoped to the actor
		*  that created it. Jobs started in PromptaFlow's own UI are shown by PromptaFlow's own
		*  UI, which has the whole authoring surface. */
		authoringByWorkspace = /* @__PURE__ */ new Map();
		bridges = /* @__PURE__ */ new Map();
		/** One entry per live Bridge: the Workspaces worth knowing the Workflows of. */
		bridgedWorkspaces = /* @__PURE__ */ new Map();
		/** Live authoring consumers, keyed by the exact Harness Session they drive. */
		authoringWaiters = /* @__PURE__ */ new Map();
		/** The last thing that went wrong while writing a Workflow here. */
		authoringTrouble = /* @__PURE__ */ new Map();
		bridgeDiagnostics = /* @__PURE__ */ new Map();
		/** Sessions whose model has already received the one-time recovery check. */
		recoveryPromptedSessions = /* @__PURE__ */ new Set();
		/** Deleted Workflows the panel still has to name, by Workspace and id. */
		retiredNames = /* @__PURE__ */ new Map();
		hostSessions;
		attachments;
		workspaceRegistry;
		constructor(ctx) {
			super(ctx, "promptaflow");
			this.hostSessions = ctx.get("sessions");
			this.attachments = ctx.get("attachments");
			this.workspaceRegistry = ctx.get("workspaceRegistry");
			this.agents = ctx.get("agents");
			new PromptaFlowToolBridge(ctx, this.gateway, (workspace, sessionId, job) => {
				this.watchAuthoring(workspace, sessionId, job);
			}).register();
			this.registerWebApi(ctx);
			this.tellTheModelWhatCanRun(ctx);
			for (const session of this.hostSessions.list()) this.startSessionBridge(ctx, session);
			ctx.on("session/created", (session) => {
				this.startSessionBridge(ctx, session);
			}, { global: true });
			ctx.on("session/disposed", (session) => {
				this.stopSessionBridge(String(session.id));
			}, { global: true });
			ctx.effect(() => () => {
				for (const controller of this.bridges.values()) controller.abort();
				this.bridges.clear();
				for (const controller of this.authoringWaiters.values()) controller.abort();
				this.authoringWaiters.clear();
			}, "promptaflow: stop Session Bridges");
		}
		/**
		* Name the runnable Workflows in the model's context, so it does not have to
		* ask before it can tell whether PromptaFlow is relevant to what was just said.
		*
		* The contribution is read synchronously at every assembly, so it can only
		* ever report what has already been fetched: a stale entry answers now and
		* refreshes for next time. The alternative — blocking assembly on a Runtime
		* that may not be running — would make a missing PromptaFlow everyone's problem.
		*/
		tellTheModelWhatCanRun(ctx) {
			const systemPrompt = ctx.get("systemPrompt");
			if (!systemPrompt) return;
			ctx.effect(() => systemPrompt.context({
				name: "promptaflow-workflows",
				order: 190,
				text: (context) => {
					const session = context.agent?.session;
					if (session === void 0) return "";
					const sessionId = String(session.id);
					const workspace = this.bridgedWorkspaces.get(String(session.id)) ?? (session.header.cwd === void 0 ? void 0 : [...this.bridgedWorkspaces.values()].find((item) => item.canonicalPath === session.header.cwd));
					if (workspace === void 0) return "";
					let recovery = "";
					if (!this.recoveryPromptedSessions.has(sessionId)) {
						this.recoveryPromptedSessions.add(sessionId);
						recovery = "[PROMPTAFLOW SESSION RECOVERY]\nOn this Session's first user turn, call promptaflow_list_delegations once. If the returned list is empty, do not mention recovery. If it contains work, tell the user what is resumable and ask whether to continue or reconcile it. Never execute an unknown delegation again.";
					}
					if (this.catalog.stale(workspace.canonicalPath)) this.refreshCatalog(workspace);
					return [recovery, this.catalog.render(workspace.canonicalPath)].filter(Boolean).join("\n\n");
				}
			}), "promptaflow: runnable Workflows in the model context");
		}
		/**
		* Read a Workspace's Workflows into the catalog; a failure leaves the last
		* answer standing.
		*
		* The parameter is a `scope` and not a `workspace` because that is what it
		* is: every caller derived it from a Session. The name is also what the
		* bundle's guard reads, so calling it anything else is how this stops being
		* checked.
		*/
		watchAuthoring(workspace, sessionId, job) {
			const held = this.authoringByWorkspace.get(workspace.canonicalPath) ?? /* @__PURE__ */ new Map();
			held.set(job.job_id, {
				sessionId,
				job
			});
			this.authoringByWorkspace.set(workspace.canonicalPath, held);
		}
		/**
		* Bring the tracked jobs up to date, and say which of them are worth drawing.
		*
		* Reports whether one of them has just published, which is the one case
		* where this Host knows the catalog it holds is out of date without being
		* told — so the caller re-reads rather than making a person press refresh
		* for a Workflow they asked for and watched arrive.
		*/
		async readAuthoring(scope) {
			const held = this.authoringByWorkspace.get(scope.canonicalPath);
			if (!held?.size) return {
				jobs: [],
				published: false
			};
			let published = false;
			const now = Date.now();
			for (const [jobId, tracked] of [...held]) {
				if (tracked.settledAt !== void 0) {
					if (now - tracked.settledAt > AUTHORING_LINGER_MS) held.delete(jobId);
					else if (tracked.job.status === "done" && !tracked.catalogRefreshed) published = true;
					continue;
				}
				try {
					tracked.job = await this.gateway.call(scope, tracked.sessionId, "get_authoring_job", { job_id: jobId });
				} catch {
					continue;
				}
				if (tracked.job.status === "queued" || tracked.job.status === "running") continue;
				tracked.settledAt = now;
				if (tracked.job.status === "done") published = true;
			}
			return {
				published,
				jobs: [...held.values()].map(({ job }) => ({
					job_id: job.job_id,
					status: job.status,
					prompt: job.prompt,
					requested_agent: job.requested_agent ?? null,
					workflow_id: job.workflow_id ?? null,
					error: job.error?.message ?? null,
					output_href: job.output_href ?? null
				}))
			};
		}
		markPublishedCatalogRefreshed(scope) {
			for (const tracked of this.authoringByWorkspace.get(scope.canonicalPath)?.values() ?? []) if (tracked.job.status === "done") tracked.catalogRefreshed = true;
		}
		async getAuthoringOutput(sessionId, outputHref, after, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			return await this.gateway.authoringOutput(scope, sessionId, outputHref, after);
		}
		refreshCatalog(scope) {
			return this.gateway.call(scope, "catalog", "list_workflows", {}).then((result) => {
				this.catalog.remember(scope.canonicalPath, result.workflows);
				return true;
			}).catch(() => false);
		}
		registerWebApi(ctx) {
			let registered = false;
			const mount = () => {
				if (registered) return;
				const webServer = ctx.get("webServer") ?? ctx.get("httpServer");
				if (!webServer) return;
				registered = true;
				/**
				* Hand a browser the bytes of one Artifact.
				*
				* A GET, because a link is what a person clicks and a browser is what
				* renders the result. It exists because PromptaFlow's own address for an
				* Artifact cannot serve one: Artifacts are owned by the actor that
				* produced them, a browser reaching `/api/v1` on loopback is `local`,
				* and the Runs this panel starts belong to `harness:session:<id>`. So
				* the link was a 404 for every Artifact this Harness ever made.
				*
				* This route is that identity. It reads the Artifact as the Session that
				* owns it and passes the bytes through unchanged — no gallery, no
				* viewer, no second drawing of anything PromptaFlow draws. The browser opens
				* what it was given, exactly as it would have from PromptaFlow's own URL.
				*/
				ctx.effect(() => webServer.register({
					kind: "exact",
					path: "/plugins/dsh-promptaflow/artifact",
					handler: async (req, res) => {
						const send = (status, body) => {
							res.writeHead(status, {
								"content-type": "text/plain; charset=utf-8",
								"cache-control": "no-store"
							});
							res.end(body);
						};
						try {
							if (req.method !== "GET") return send(405, "GET only");
							const query = new URL(req.url ?? "", "http://localhost").searchParams;
							const sessionId = query.get("session") ?? "";
							const artifactId = query.get("id") ?? "";
							if (!sessionId || !artifactId) return send(400, "session and id are required");
							const scope = await this.sessionWorkspace(sessionId);
							const held = await this.gateway.call(scope, sessionId, "read_artifact_content", { artifact_id: artifactId });
							const bytes = Buffer.from(held.content, "base64");
							res.writeHead(200, {
								"content-type": String(held.artifact.content_type || "application/octet-stream"),
								"content-length": String(bytes.length),
								"cache-control": "no-store",
								"content-security-policy": "sandbox; default-src 'none'",
								"x-content-type-options": "nosniff",
								...typeof held.artifact.filename === "string" && held.artifact.filename ? { "content-disposition": `inline; filename*=UTF-8''${encodeURIComponent(held.artifact.filename)}` } : {}
							});
							res.end(bytes);
						} catch (error) {
							send(404, String(error));
						}
					}
				}), "promptaflow: Artifact bytes for a browser link");
				ctx.effect(() => webServer.register({
					kind: "exact",
					path: "/plugins/dsh-promptaflow/api",
					handler: async (req, res) => {
						if (req.method !== "POST") {
							res.writeHead(405, { allow: "POST" });
							res.end();
							return;
						}
						const controller = new AbortController();
						req.once("aborted", () => controller.abort(/* @__PURE__ */ new Error("PromptaFlow client request aborted")));
						try {
							const chunks = [];
							let size = 0;
							for await (const chunk of req) {
								const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
								size += buffer.length;
								if (size > 262144) {
									req.destroy();
									throw new Error("PromptaFlow client request exceeds 256 KiB");
								}
								chunks.push(buffer);
							}
							const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
							if (typeof body.action !== "string" || !Array.isArray(body.args)) throw new Error("PromptaFlow client request requires action and args");
							const result = await this.dispatchWebApi(body.action, body.args, controller.signal);
							res.writeHead(200, {
								"content-type": "application/json; charset=utf-8",
								"cache-control": "no-store"
							});
							res.end(JSON.stringify({ result: result === void 0 ? null : result }));
						} catch (error) {
							res.writeHead(400, {
								"content-type": "application/json; charset=utf-8",
								"cache-control": "no-store"
							});
							res.end(JSON.stringify({ error: String(error) }));
						}
					}
				}), "promptaflow: browser Host API");
			};
			mount();
			ctx.on("internal/service", (name) => {
				if (name === "webServer" || name === "httpServer") mount();
			});
		}
		async dispatchWebApi(action, args, signal) {
			switch (action) {
				case "getRuntime": return await this.getRuntime(args[0], signal);
				case "getRuntimeUi": return await this.getRuntimeUi(String(args[0]), signal);
				case "getPanelState": return await this.getPanelState(String(args[0]), Boolean(args[1]), Boolean(args[2]), signal);
				case "getAuthoringOutput": return await this.getAuthoringOutput(String(args[0]), String(args[1]), Number(args[2]), signal);
				case "getRunDetail": return await this.getRunDetail(String(args[0]), String(args[1]), signal);
				case "getWorkflowDefinition": return await this.getWorkflowDefinition(String(args[0]), String(args[1]), signal);
				case "getStepOutput": return await this.getStepOutput(String(args[0]), String(args[1]), String(args[2]), Number(args[3]), signal);
				case "runCommand": return await this.runCommand(String(args[0]), String(args[1]), args[2], Number(args[3]), args[4], args[5] === void 0 ? void 0 : String(args[5]), signal);
				case "reconcileStep": return await this.reconcileStep(String(args[0]), String(args[1]), String(args[2]), args[3], String(args[4]), signal);
				case "exportArtifact": return await this.exportArtifact(String(args[0]), String(args[1]), signal);
				case "readArtifactText": return await this.readArtifactText(String(args[0]), String(args[1]), signal);
				case "getDiagnostics": return await this.getDiagnostics(args[0], String(args[1]), signal);
				case "stopRuntime": return await this.stopRuntime(String(args[0]), signal);
				case "listWorkflows": return await this.listWorkflows(args[0], String(args[1]), signal);
				case "listRuns": return await this.listRuns(args[0], String(args[1]), args[2] === void 0 ? void 0 : String(args[2]), signal);
				case "generateWorkflow": return await this.generateWorkflow(args[0], String(args[1]), String(args[2]), signal);
				case "modifyWorkflow": return await this.modifyWorkflow(args[0], String(args[1]), String(args[2]), String(args[3]), Boolean(args[4]), signal);
				case "getAuthoringJob": return await this.getAuthoringJob(args[0], String(args[1]), String(args[2]), signal);
				case "getRun": return await this.getRun(args[0], String(args[1]), String(args[2]), signal);
				case "getSteps": return await this.getSteps(args[0], String(args[1]), String(args[2]), signal);
				case "getGraph": return await this.getGraph(args[0], String(args[1]), String(args[2]), signal);
				case "getEdges": return await this.getEdges(args[0], String(args[1]), String(args[2]), signal);
				case "readOutput": return await this.readOutput(args[0], String(args[1]), String(args[2]), Number(args[3]), args[4] === void 0 ? void 0 : String(args[4]), signal);
				case "listArtifacts": return await this.listArtifacts(args[0], String(args[1]), args[2] === void 0 ? void 0 : String(args[2]), signal);
				case "getArtifactContent": return await this.getArtifactContent(args[0], String(args[1]), String(args[2]), signal);
				case "importArtifact": return await this.importArtifact(args[0], String(args[1]), String(args[2]), signal);
				case "executeCommand": return await this.executeCommand(args[0], signal);
				case "reconcileDelegation": return await this.reconcileDelegation(args[0], String(args[1]), String(args[2]), String(args[3]), args[4], String(args[5]), signal);
				default: throw new Error(`Unknown PromptaFlow client action: ${action}`);
			}
		}
		/**
		* Turn a caller-supplied Workspace into one this Host vouches for.
		*
		* The browser sends a Workspace with every call, and a browser is not an
		* authority on which directory a Session belongs to: the Session is. A
		* mismatch is refused rather than quietly corrected, because the two
		* disagreeing at all means the caller is describing a Session it is not in.
		*/
		async verified(claimed, sessionId) {
			const actual = await this.workspaceForSession(this.liveSession(sessionId));
			if (claimed.id !== actual.id || claimed.canonicalPath !== actual.canonicalPath) throw new Error("PromptaFlow request Workspace does not match the Harness Session");
			return actual;
		}
		/**
		* The same guarantee for the Settings panel, which has a Workspace but no
		* Session. Its authority is the Workspace registry: a path nobody registered
		* is not somewhere this Host will go looking for a Runtime.
		*/
		async registered(claimed) {
			const found = await this.workspaceRegistry.resolveByPath(claimed.canonicalPath);
			if (!found || String(found.id) !== claimed.id || found.path !== claimed.canonicalPath) throw new Error("PromptaFlow request names a Workspace this Harness has not registered");
			return {
				id: String(found.id),
				canonicalPath: found.path
			};
		}
		/**
		* The Workspace of a Session, derived and never claimed.
		*
		* Stronger than `verified`: there is no caller-supplied value to disagree
		* with, so there is nothing to check.
		*/
		async sessionWorkspace(sessionId, allowPersisted = false) {
			return (await this.sessionScope(sessionId, allowPersisted)).scope;
		}
		/**
		* The Workspace of a Session, and whether the Session was actually there.
		*
		* The second half matters to one caller: what may be read from the durable
		* registry during the window before a persisted conversation enters its Host
		* Session is a projection, and a projection does not start processes. The
		* panel asks for both so it can decline to launch a Runtime for a Workspace
		* no live Session vouched for.
		*/
		async sessionScope(sessionId, allowPersisted = false) {
			const live = this.hostSessions.list().find((item) => String(item.id) === sessionId);
			if (live) return {
				scope: await this.workspaceForSession(live),
				live: true
			};
			if (allowPersisted) {
				const matches = this.workspaceRegistry.list().filter((workspace) => workspace.sessionIds.some((id) => String(id) === sessionId));
				if (matches.length === 1) return {
					scope: {
						id: String(matches[0].id),
						canonicalPath: matches[0].path
					},
					live: false
				};
				if (matches.length > 1) throw new Error("PromptaFlow requires a live Harness Session");
			}
			throw new Error("PromptaFlow requires a live Harness Session");
		}
		liveSession(sessionId) {
			const session = this.hostSessions.list().find((item) => String(item.id) === sessionId);
			if (!session) throw new Error("PromptaFlow requires a live Harness Session");
			return session;
		}
		startSessionBridge(ctx, session) {
			const sessionId = String(session.id);
			if (this.bridges.has(sessionId) || !sessionCanBridge(session.header)) return;
			const cwd = session.header.cwd;
			if (!cwd) return;
			const controller = new AbortController();
			this.bridges.set(sessionId, controller);
			this.bridgeDiagnostics.set(sessionId, {
				state: "connecting",
				cursorPosition: 0,
				updatedAt: (/* @__PURE__ */ new Date()).toISOString()
			});
			this.bindSessionWorkspace(ctx, session, cwd).finally(() => {
				if (this.bridges.get(sessionId) === controller) this.bridges.delete(sessionId);
			});
		}
		stopSessionBridge(sessionId) {
			this.bridges.get(sessionId)?.abort();
			this.bridges.delete(sessionId);
			this.bridgeDiagnostics.delete(sessionId);
			this.recoveryPromptedSessions.delete(sessionId);
			const workspace = this.bridgedWorkspaces.get(sessionId);
			this.bridgedWorkspaces.delete(sessionId);
			if (workspace !== void 0 && ![...this.bridgedWorkspaces.values()].some((item) => item.canonicalPath === workspace.canonicalPath)) this.catalog.forget(workspace.canonicalPath);
			this.authoringWaiters.get(sessionId)?.abort();
			this.authoringWaiters.delete(sessionId);
		}
		/**
		* Bind a Session to the Workspace it is working in, and warm that catalog.
		*
		* Warmed before the first turn asks, because this runs when the Session is
		* created and the person types afterwards. The binding is what
		* `tellTheModelWhatCanRun` reads, so every Session that can reach a Runtime
		* is registered here whether or not anything else happens.
		*
		* This is all that happens at Session start now. It used to also run
		* `PromptaFlowSessionBridge`, which recorded each Run into the Session log as
		* `promptaflow/run-started` / `-checkpoint` / `-ended`; see `stopSessionBridge`
		* and the note on why that stopped.
		*/
		async bindSessionWorkspace(ctx, session, cwd) {
			const registered = await ctx.workspaceRegistry.resolveByPath(cwd);
			const workspace = {
				id: registered ? String(registered.id) : `cwd:${cwd}`,
				canonicalPath: registered?.path ?? cwd
			};
			this.bridgedWorkspaces.set(String(session.id), workspace);
			this.refreshCatalog(workspace);
			this.bridgeDiagnostics.set(String(session.id), {
				state: "bound",
				cursorPosition: 0,
				updatedAt: (/* @__PURE__ */ new Date()).toISOString()
			});
			this.waitForAuthoring(ctx, workspace, String(session.id));
		}
		/**
		* Stand on PromptaFlow's authoring queue for this Workspace, and write what comes.
		*
		* Being on the queue is what makes this Host a writer PromptaFlow will choose:
		* `_connected_client_first` prefers a connected client over forking an Agent
		* CLI, and it counts a client as connected because it is waiting here. A
		* Host that only ever called tools was never on the queue, so the preference
		* had nothing to prefer and every Workflow was written by a forked CLI whose
		* work nobody could watch.
		*
		* Restarted after every wait, including after a failure, because the wait is
		* how the Host stays addressable — stopping on the first unreachable Runtime
		* would take this Workspace off the menu until the Session was recreated.
		*/
		waitForAuthoring(ctx, scope, sessionId) {
			if (this.authoringWaiters.has(sessionId)) return;
			const controller = new AbortController();
			this.authoringWaiters.set(sessionId, controller);
			const client = authoringClientForSession(sessionId);
			const loop = async () => {
				while (!controller.signal.aborted) {
					const outcome = await claimOnce({
						wait: async (seconds) => await this.gateway.call(scope, sessionId, "wait_authoring_request", {
							client,
							timeout_seconds: seconds
						}).then((result) => result.request),
						ask: async (prompt) => await this.askTheSession(sessionId, prompt),
						submit: async (requestId, dsl) => await this.gateway.call(scope, sessionId, "submit_authoring_response", {
							request_id: requestId,
							dsl
						}),
						report: (stage, error) => {
							this.authoringTrouble.set(scope.canonicalPath, {
								stage,
								error: String(error),
								at: (/* @__PURE__ */ new Date()).toISOString()
							});
							ctx.logger.warn(`PromptaFlow authoring ${stage} failed in ${scope.canonicalPath}: ${String(error)}`);
						}
					});
					if (controller.signal.aborted) return;
					if (outcome === "failed") await new Promise((resolve) => {
						const timer = setTimeout(resolve, CLAIM_RETRY_MS);
						controller.signal.addEventListener("abort", () => {
							clearTimeout(timer);
							resolve();
						}, { once: true });
					});
				}
			};
			loop().finally(() => {
				if (this.authoringWaiters.get(sessionId) === controller) this.authoringWaiters.delete(sessionId);
			});
		}
		/**
		* Put the prompt to the Workspace's Session and return what its model said.
		*
		* `followup` rather than anything quieter: the whole point is that the work
		* happens in the conversation, where a person can watch it and where the
		* Agent has the context the request came out of. It becomes an ordinary turn
		* and queues behind whatever the person is doing, so this never interrupts
		* one — it waits for one to end.
		*
		* The answer is read back out of the Session's own log rather than returned
		* by the call, because the log is what actually happened: a turn that used
		* tools answers across several messages, and the log has all of them in
		* order.
		*/
		async askTheSession(sessionId, prompt) {
			if (this.agents === void 0) throw new Error("this Harness exposes no Agent registry");
			const agent = this.agents.get(sessionId);
			if (agent === void 0) throw new Error(`no live Agent for Session ${sessionId}`);
			const mark = agent.session.events.length;
			agent.followup(createUserMessage({
				content: [{
					type: "text",
					text: prompt
				}],
				source: {
					kind: "plugin",
					plugin: "promptaflow"
				}
			}));
			const deadline = Date.now() + AUTHORING_TURN_MS;
			for (;;) {
				await agent.whenIdle();
				const said = answerFrom(agent.session.events, mark);
				if (said.trim()) return said;
				if (Date.now() >= deadline) return "";
				await new Promise((resolve) => setTimeout(resolve, 1e3));
			}
		}
		/**
		* Drive the Session Bridge for one Session, writing each Run into its log.
		*
		* NOT called at Session start, and must not be until the Harness can accept
		* the events it writes. `promptaflow/run-*` are not in the Harness's own event
		* vocabulary, and `Session.append` offers no way to set the envelope's
		* `ignorable` marker — the one thing that lets a reader skip a type it does
		* not know. So every Session this ran in became unreadable on reload:
		*
		*   session "…" contains event type "promptaflow/run-started" (seq 964) unknown to
		*   this harness and not marked ignorable; refusing to interpret the log
		*
		* Kept rather than deleted because nothing here is wrong except where the
		* record is put. `@deepseek-ai/dsh-session` says a registration surface for
		* out-of-repo plugin events "is deferred until such a consumer exists"; this
		* is that consumer. When `append` can mark an event ignorable, or the
		* vocabulary can be extended, calling this from `bindSessionWorkspace`
		* restores the account of what ran.
		*/
		async bridgeSession(workspace, session, cursor, signal, knownRuns = []) {
			await new PromptaFlowSessionBridge(this.gateway, cursor).run(workspace, String(session.id), { append: async (event) => {
				const { type, ...data } = event;
				session.append(type, data);
				await this.hostSessions.flush(session);
			} }, signal, knownRuns);
		}
		async getRuntime(workspace, signal) {
			signal.throwIfAborted();
			const scope = await this.registered(workspace);
			const release = await this.gateway.acquire(scope);
			try {
				const capabilities = await this.gateway.call(scope, "probe", "get_capabilities", {});
				return {
					workspaceId: scope.id,
					state: "ready",
					capabilities
				};
			} finally {
				await release();
			}
		}
		async getRuntimeUi(sessionId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.uiUrl(scope);
			} finally {
				await release();
			}
		}
		/**
		* Everything the resident panel draws, in one round trip.
		*
		* It takes a Session and derives the Workspace, so a poller that runs every
		* couple of seconds carries no claim the Host has to check — and the panel
		* never has to know what a Workspace is.
		*/
		/**
		* Everything the panel draws, in one call.
		*
		* `force` is a person pressing refresh, and it is the difference between a
		* poll and an answer: the catalog and the Agent registry are both held
		* deliberately — one behind a TTL, one for the life of the Runtime — because
		* a two-second poll must not re-ask questions that change when somebody
		* publishes. A press is exactly the case where they may have.
		*/
		async getPanelState(sessionId, force, startIfMissing, signal) {
			signal.throwIfAborted();
			const { scope, live } = await this.sessionScope(sessionId, true);
			const release = await this.gateway.acquire(scope, startIfMissing && live);
			try {
				const result = await this.gateway.call(scope, sessionId, "list_runs", { limit: 50 });
				const authoring = await this.readAuthoring(scope);
				if (force || authoring.published) {
					const refreshed = await this.refreshCatalog(scope);
					if (authoring.published && refreshed) this.markPublishedCatalogRefreshed(scope);
				} else if (this.catalog.stale(scope.canonicalPath)) this.refreshCatalog(scope);
				const agents = (await this.gateway.call(scope, sessionId, "list_agents", {})).agents;
				const workflows = this.catalog.list(scope.canonicalPath);
				const retired = await this.retiredWorkflowNames(scope, sessionId, result.runs, workflows, force);
				const runs = result.runs.filter((run) => !retired.missing.has(run.workflow_id));
				return {
					runs,
					uiUrl: await this.gateway.uiUrl(scope),
					workflows,
					agents,
					retiredWorkflowNames: retired.names,
					authoring: authoring.jobs,
					steps: await this.liveSteps(scope, sessionId, runs)
				};
			} finally {
				await release();
			}
		}
		/**
		* Names for the Workflows a Run ran and the catalog no longer offers.
		*
		* Deleting a Workflow retires its id; it does not retract the Runs that
		* carry it, which go on executing and being opened. The catalog is the
		* wrong place to look one of those up — a catalog is what can be started —
		* so the panel had nothing to name them by and printed the id, which reads
		* as a Goal pointed at something that is not there. PromptaFlow keeps the
		* definition for exactly this, so ask it.
		*
		* Read once per id and remembered, negative answers included: a retired id
		* is never reissued, so neither answer can go out of date, and a poll that
		* runs every couple of seconds must not re-ask either one.
		*
		* `force` is the refresh button, and it clears what is held here as well.
		* A negative is only as immutable as the database it was asked of: a
		* Runtime pointed at the wrong one answers "not found" for every id, and
		* those answers would then hide those Runs for the life of the Host.
		*/
		async retiredWorkflowNames(scope, sessionId, runs, listed, force = false) {
			const offered = new Set(listed.map((item) => item.workflow_id));
			const retired = [...new Set(runs.map((run) => run.workflow_id))].filter((id) => !offered.has(id));
			if (force) for (const id of retired) this.retiredNames.delete(this.retiredKey(scope, id));
			await Promise.all(retired.filter((id) => !this.retiredNames.has(this.retiredKey(scope, id))).map(async (id) => {
				try {
					const definition = await this.gateway.call(scope, sessionId, "inspect_workflow_definition", { workflow_id: id });
					this.retiredNames.set(this.retiredKey(scope, id), definition.name || "");
				} catch (reason) {
					const detail = reason instanceof Error ? reason.message : String(reason);
					if (/workflow (?:version )?not found/iu.test(detail)) this.retiredNames.set(this.retiredKey(scope, id), null);
				}
			}));
			const names = {};
			const missing = /* @__PURE__ */ new Set();
			for (const id of retired) {
				const held = this.retiredNames.get(this.retiredKey(scope, id));
				if (held) names[id] = held;
				else if (held === null) missing.add(id);
			}
			return {
				names,
				missing
			};
		}
		retiredKey(scope, workflowId) {
			return `${scope.canonicalPath}\n${workflowId}`;
		}
		/**
		* The steps of the Runs that are still moving, so the Goal page can draw them.
		*
		* Only the live ones, and only what that page draws: the name and status of
		* each step, whether it has output to offer, and whether it is waiting on a
		* person. The rest of a StepSummary — the prompt it was authored with, its
		* handler, its timestamps — is detail nobody reads here, and sending the
		* whole thing on a two-second poll would put a page of JSON on the wire per
		* Run to render a list of names.
		*
		* A Run whose steps cannot be read loses its progress line and keeps its
		* row. The alternative is a panel that goes blank because one Run out of six
		* answered badly, which trades the thing a reader came for against a detail
		* they did not.
		*/
		async liveSteps(scope, sessionId, runs) {
			const drawn = goalRuns(runs.map((run) => ({
				live: isLive(run.status),
				updatedAt: run.updated_at,
				run
			}))).slice(0, LIVE_STEP_LIMIT);
			const read = await Promise.all(drawn.map(async ({ run }) => {
				try {
					const detail = await this.gateway.call(scope, sessionId, "get_run_steps", { run_id: run.run_id });
					return [run.run_id, detail.steps.map((step) => ({
						node_id: step.node_id,
						label: step.label,
						status: step.status,
						has_output: step.has_output,
						resolution: step.resolution,
						reconciliation: step.reconciliation
					}))];
				} catch {
					return null;
				}
			}));
			return Object.fromEntries(read.filter((entry) => entry !== null));
		}
		/**
		* The steps of one Run, for a panel row the reader opened.
		*
		* Session-scoped like the panel's poll: a Run id is not a capability, so the
		* Workspace it is read in comes from the Session rather than from the caller.
		*/
		async getRunDetail(sessionId, runId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "get_run_steps", { run_id: runId });
			} finally {
				await release();
			}
		}
		/**
		* The steps one Workflow is published with — read on demand, never polled.
		*
		* A definition changes only when someone republishes it, so this is fetched
		* when a reader opens a Workflow and not again.
		*/
		async getWorkflowDefinition(sessionId, workflowId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "get_workflow_definition", { workflow_id: workflowId });
			} finally {
				await release();
			}
		}
		async getStepOutput(sessionId, runId, nodeId, after, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "read_run_output", {
					run_id: runId,
					after,
					node_id: nodeId
				});
			} finally {
				await release();
			}
		}
		/**
		* Cancel or resume a Run from the panel.
		*
		* `expectedRevision` is what the panel had on screen, and it must still be
		* what PromptaFlow advertises. Re-reading here would make the call succeed against
		* a Run that changed under the reader — the refusal is the point: whoever
		* pressed the button was looking at something else.
		*/
		async runCommand(sessionId, runId, command, expectedRevision, value, interruptId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				const advertised = advertisedAt(await this.gateway.run(scope, sessionId, runId), command, expectedRevision);
				if (advertised === void 0) throw new Error(`PromptaFlow no longer offers ${command} at revision ${String(expectedRevision)}`);
				return await this.gateway.call(scope, sessionId, commandTool(command), {
					run_id: runId,
					expected_version: advertised.expected_version,
					idempotency_key: crypto.randomUUID(),
					...value === void 0 ? {} : { value },
					...interruptId === void 0 ? {} : { interrupt_id: interruptId }
				});
			} finally {
				await release();
			}
		}
		/** Record a person's ruling on what an external Agent actually did. */
		async reconcileStep(sessionId, runId, delegationId, outcome, note, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				await this.gateway.call(scope, sessionId, "reconcile_delegation", {
					delegation_id: delegationId,
					outcome,
					note,
					idempotency_key: crypto.randomUUID()
				});
				return await this.gateway.call(scope, sessionId, "get_run_steps", { run_id: runId });
			} finally {
				await release();
			}
		}
		/**
		* Stop the PromptaFlow Runtime serving this Session's Workspace.
		*
		* Session-scoped like every other call here: the Workspace is derived from
		* the Session rather than taken from the caller, so this can only ever stop
		* the Runtime the person is actually looking at.
		*
		* The waiter goes first. It is parked on that Runtime's authoring queue, and
		* leaving it there would have it discover the shutdown as a transport error
		* and log one — a failure report about something that was asked for.
		*/
		async stopRuntime(sessionId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId);
			this.authoringWaiters.get(scope.canonicalPath)?.abort();
			this.authoringWaiters.delete(scope.canonicalPath);
			await this.gateway.stopRuntime(scope, sessionId);
			return { stopped: true };
		}
		async getDiagnostics(workspace, sessionId, signal) {
			const runtime = await this.getRuntime(workspace, signal);
			return {
				generated_at: (/* @__PURE__ */ new Date()).toISOString(),
				workspace_id: workspace.id,
				session_id: sessionId,
				runtime,
				gateway: this.gateway.diagnostics(),
				bridge: this.bridgeDiagnostics.get(sessionId) || null,
				authoring: {
					waiting: this.authoringWaiters.has(sessionId),
					driving: this.authoringWaiters.has(sessionId) ? sessionId : null,
					agentRegistry: this.agents !== void 0,
					lastError: this.authoringTrouble.get(workspace.canonicalPath) ?? null
				}
			};
		}
		async listWorkflows(workspace, sessionId, signal) {
			return await this.readListField(workspace, sessionId, "list_workflows", "workflows", {}, signal);
		}
		async listRuns(workspace, sessionId, status, signal) {
			return await this.readListField(workspace, sessionId, "list_runs", "runs", {
				limit: 100,
				...status ? { status } : {}
			}, signal);
		}
		async workspaceForSession(session) {
			const cwd = session.header.cwd;
			if (!cwd) throw new Error("PromptaFlow requires the Harness Session to have a Workspace cwd");
			const registered = await this.workspaceRegistry.resolveByPath(cwd);
			return {
				id: registered ? String(registered.id) : `cwd:${cwd}`,
				canonicalPath: registered?.path ?? cwd
			};
		}
		async generateWorkflow(workspace, sessionId, prompt, signal) {
			signal.throwIfAborted();
			if (!prompt.trim() || prompt.length > 2e4) throw new Error("Workflow prompt must be 1-20000 characters");
			const scope = await this.verified(workspace, sessionId);
			const agent = await this.prepareAuthoringRoute(scope, sessionId);
			const job = await this.gateway.call(scope, sessionId, "generate_workflow", {
				prompt: prompt.trim(),
				display_language: "zh-CN",
				agent,
				idempotency_key: crypto.randomUUID()
			});
			this.watchAuthoring(scope, sessionId, job);
			return job;
		}
		/** Register this exact Session route before asking PromptaFlow to address work to it. */
		async prepareAuthoringRoute(scope, sessionId) {
			const client = authoringClientForSession(sessionId);
			await this.gateway.call(scope, sessionId, "register_authoring_client", { client });
			return client;
		}
		async modifyWorkflow(workspace, sessionId, workflowId, prompt, regenerate, signal) {
			signal.throwIfAborted();
			if (!workflowId.trim()) throw new Error("Workflow id is required");
			if (!prompt.trim() || prompt.length > 2e4) throw new Error("Workflow prompt must be 1-20000 characters");
			const scope = await this.verified(workspace, sessionId);
			const agent = await this.prepareAuthoringRoute(scope, sessionId);
			return await this.gateway.call(scope, sessionId, "modify_workflow", {
				workflow_id: workflowId,
				prompt: prompt.trim(),
				mode: regenerate ? "regenerate" : "modify",
				display_language: "zh-CN",
				agent,
				idempotency_key: crypto.randomUUID()
			});
		}
		async getAuthoringJob(workspace, sessionId, jobId, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			return await this.gateway.call(scope, sessionId, "get_authoring_job", { job_id: jobId });
		}
		async getRun(workspace, sessionId, runId, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.run(scope, sessionId, runId);
			} finally {
				await release();
			}
		}
		async getSteps(workspace, sessionId, runId, signal) {
			return await this.readRunField(workspace, sessionId, runId, "get_run_steps", "steps", signal);
		}
		async getGraph(workspace, sessionId, runId, signal) {
			return await this.readRunField(workspace, sessionId, runId, "get_run_graph", "graph", signal);
		}
		async getEdges(workspace, sessionId, runId, signal) {
			return await this.readRunField(workspace, sessionId, runId, "get_run_edges", "edges", signal);
		}
		async readOutput(workspace, sessionId, runId, after, nodeId, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "read_run_output", {
					run_id: runId,
					after,
					...nodeId ? { node_id: nodeId } : {}
				});
			} finally {
				await release();
			}
		}
		async listArtifacts(workspace, sessionId, runId, signal) {
			return await this.readListField(workspace, sessionId, "list_artifacts", "artifacts", {
				limit: 100,
				...runId ? { run_id: runId } : {}
			}, signal);
		}
		async getArtifact(workspace, sessionId, artifactId, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "read_artifact", { artifact_id: artifactId });
			} finally {
				await release();
			}
		}
		async getArtifactContent(workspace, sessionId, artifactId, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return await this.gateway.call(scope, sessionId, "read_artifact_content", { artifact_id: artifactId });
			} finally {
				await release();
			}
		}
		/**
		* What an Artifact is, and its text when its text is the answer.
		*
		* Metadata first, always: a workflow that writes its reply as markdown has
		* written the reply, and making a reader click through to it charges them a
		* click for the thing they asked for. But asking for a 2 MiB PDF in order to
		* discover it is a 2 MiB PDF is the round trip this ordering avoids, so the
		* bytes are fetched only once the recorded type and size say they are worth
		* fetching.
		*/
		async readArtifactText(sessionId, artifactId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId, true);
			const meta = await this.gateway.call(scope, sessionId, "read_artifact", { artifact_id: artifactId });
			const contentType = String(meta.content_type ?? "");
			const sizeBytes = Number(meta.size_bytes ?? 0);
			if (!readableAsText(contentType, sizeBytes)) return {
				contentType,
				sizeBytes,
				text: null
			};
			const held = await this.gateway.call(scope, sessionId, "read_artifact_content", { artifact_id: artifactId });
			return {
				contentType,
				sizeBytes,
				text: Buffer.from(held.content, "base64").toString("utf8")
			};
		}
		/**
		* Write one Artifact out as an ordinary file and say where it went.
		*
		* Not the path it already has. PromptaFlow stores Artifacts content-addressed: the
		* file on disk is named by the sha256 of its own bytes, has no extension, is
		* shared by every Artifact with identical content, and is collected when
		* nothing references it. Handing that path to a person invites them to open
		* it in an editor and save — and saving corrupts every Artifact sharing
		* those bytes. So they get a copy that is theirs.
		*
		* Session-scoped like everything else here, and for the same reason twice
		* over: an Artifact belongs to the actor that produced it, so the Session is
		* both which Workspace to look in and the only identity allowed to read it.
		*/
		async exportArtifact(sessionId, artifactId, signal) {
			signal.throwIfAborted();
			const scope = await this.sessionWorkspace(sessionId);
			const held = await this.gateway.call(scope, sessionId, "read_artifact_content", { artifact_id: artifactId });
			const target = join(homedir(), "Downloads", artifactFilename(artifactId, held.artifact.content_type, held.artifact.filename));
			await mkdir(dirname(target), { recursive: true });
			await writeFile(target, Buffer.from(held.content, "base64"));
			return { path: target };
		}
		async importArtifact(workspace, sessionId, artifactId, signal) {
			const content = await this.getArtifactContent(workspace, sessionId, artifactId, signal);
			return await this.attachments.saveImage(artifactImageInput(content));
		}
		async reconcileDelegation(workspace, sessionId, runId, delegationId, outcome, note, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				await this.gateway.call(scope, sessionId, "reconcile_delegation", {
					delegation_id: delegationId,
					outcome,
					note,
					idempotency_key: crypto.randomUUID()
				});
				return (await this.gateway.call(scope, sessionId, "get_run_steps", { run_id: runId })).steps;
			} finally {
				await release();
			}
		}
		async readRunField(workspace, sessionId, runId, tool, field, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return (await this.gateway.call(scope, sessionId, tool, { run_id: runId }))[field];
			} finally {
				await release();
			}
		}
		async readListField(workspace, sessionId, tool, field, arguments_, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(workspace, sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				return (await this.gateway.call(scope, sessionId, tool, arguments_))[field];
			} finally {
				await release();
			}
		}
		async executeCommand(request, signal) {
			signal.throwIfAborted();
			const scope = await this.verified(request.workspace, request.sessionId);
			const release = await this.gateway.acquire(scope);
			try {
				if (advertisedAt(await this.gateway.run(scope, request.sessionId, request.runId), request.command, request.expectedVersion) === void 0) throw new Error("PromptaFlow command is no longer advertised at this revision");
				const tool = commandTool(request.command);
				return await this.gateway.call(scope, request.sessionId, tool, {
					run_id: request.runId,
					expected_version: request.expectedVersion,
					idempotency_key: request.idempotencyKey,
					value: request.value,
					interrupt_id: request.interruptId
				});
			} finally {
				await release();
			}
		}
	};
})();
//#endregion
export { PromptaFlowRemoteService, PromptaFlowRemoteService as default };
