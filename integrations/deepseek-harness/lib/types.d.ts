//#region ../../integration-core/src/types.d.ts
interface WorkspaceRef {
  id: string;
  canonicalPath: string;
  repositoryId?: string;
  worktreeId?: string;
  baseRevision?: string;
  isolationMode?: 'shared' | 'exclusive' | 'worktree' | 'snapshot';
}
interface RuntimeSummary {
  workspaceId: string;
  state: 'ready' | 'stopped';
  capabilities: Record<string, unknown>;
}
interface WorkflowSummary {
  workflow_id: string;
  name: string;
  description: string;
  latest_version: number;
  goal_readiness: string;
  readiness_reason?: string | null;
  input_mode?: string;
  inputs?: unknown[];
  goal_binding?: unknown;
  node_count?: number;
  node_kinds?: Record<string, number>;
}
/** One published step, as a reader meets it: what it does and who runs it. */
interface WorkflowNode {
  node_id: string;
  label: string;
  kind: string;
  handler: string | null;
  prompt: string;
}
interface AuthoringJob {
  job_id: string;
  type: string;
  workflow_id?: string | null;
  prompt: string;
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
  requested_agent?: string | null;
  attempts?: number | null;
  result?: unknown;
  error?: {
    code: string;
    message: string;
    diagnostics?: unknown[];
  } | null;
  output_href?: string | null;
  created_at: string;
  updated_at: string;
}
interface GenerateAndRunOptions {
  agent?: string;
  displayLanguage?: string;
  pollMs?: number;
  timeoutMs?: number;
}
interface GenerateAndRunResult {
  workflow: AuthoringJob;
  run: RunDto;
}
/** An authoring job as the panel draws it: what was asked, and how it went. */
interface AuthoringSummary {
  job_id: string;
  status: string;
  prompt: string;
  requested_agent?: string | null;
  workflow_id?: string | null;
  error?: string | null;
  output_href?: string | null;
}
interface AuthoringOutputChunk {
  chunk_id: number;
  stream: 'stdout' | 'stderr';
  text: string;
  created_at: string;
}
interface AuthoringOutputPage {
  chunks: AuthoringOutputChunk[];
  has_more: boolean;
}
interface OrbitCommandRequest {
  workspace: WorkspaceRef;
  sessionId: string;
  runId: string;
  command: 'langgraph_run.cancel' | 'langgraph_run.resume';
  expectedVersion: number;
  idempotencyKey: string;
  value?: unknown;
  interruptId?: string;
}
type RunDto = Record<string, unknown> & {
  run_id: string;
  goal: string;
  inputs?: Record<string, unknown>;
  workflow_id: string;
  workflow_version: number;
  status: string;
  revision: number;
  artifact_count: number;
  result?: unknown;
  error?: string | null;
  created_at: string;
  updated_at: string;
  interrupts: unknown[];
  allowed_commands: Array<{
    command: string;
    expected_version: number;
  }>;
};
interface StepSummary {
  node_id: string;
  status: string;
  has_output?: boolean;
  resolution?: {
    kind: 'reconciliation_required';
    delegation_id?: string;
  };
  reconciliation?: {
    outcome: 'confirmed_succeeded' | 'confirmed_failed';
    note: string;
    created_at: string;
  };
  [key: string]: unknown;
}
interface AgentSummary {
  name: string;
  version: string;
  node_kinds: string[];
  attempt_count?: number;
  failed_count?: number;
}
interface RunGraph {
  [key: string]: unknown;
}
interface EdgeSummary {
  edge_id: string;
  source_node: string;
  target_node: string;
  status: string;
  [key: string]: unknown;
}
interface OutputChunk {
  chunk_id: number;
  node_id: string;
  attempt_id: string;
  stream: 'stdout' | 'stderr';
  text: string;
  created_at: string;
}
interface OutputPage {
  chunks: OutputChunk[];
  after: number;
  has_more: boolean;
}
interface ArtifactSummary {
  artifact_id: string;
  run_id: string;
  content_type?: string;
  size_bytes?: number;
  filename?: string | null;
  [key: string]: unknown;
}
interface ImportedArtifact {
  attachmentId: string;
  mediaType: string;
  bytes: number;
  width: number;
  height: number;
  name?: string;
}
interface IntegrationDiagnostics {
  generated_at: string;
  workspace_id: string;
  session_id: string;
  runtime: RuntimeSummary;
  gateway: {
    discoveryAttempts: number;
    rpcCalls: number;
    transportFailures: number;
    connectedWorkspaces: number;
    lastConnectedAt?: string;
    lastTransportError?: string;
  };
  bridge: {
    state: string;
    cursorPosition: number;
    lastError?: string;
    updatedAt: string;
  } | null;
  authoring: {
    waiting: boolean;
    driving: string | null;
    agentRegistry: boolean;
    lastError: {
      stage: string;
      error: string;
      at: string;
    } | null;
  };
}
interface ArtifactContent {
  artifact: ArtifactSummary;
  encoding: 'base64';
  content: string;
}
interface RuntimeEventHint {
  position: number;
  run_id: string;
  event_type: string;
  revision: number;
  occurred_at: string;
  node_id?: string;
  attempt_id?: string;
}
interface RuntimeEventPage {
  events: RuntimeEventHint[];
  next_position: number;
}
interface OrbitRunStarted {
  type: 'orbit/run-started';
  sourcePosition: number;
  runId: string;
  workspaceId: string;
  goal: string;
  workflowId: string;
  workflowVersion: number;
  revision: number;
  status: string;
  createdAt: string;
}
interface OrbitRunCheckpoint {
  type: 'orbit/run-checkpoint';
  sourcePosition: number;
  runId: string;
  revision: number;
  status: string;
  currentSteps: StepSummary[];
  stepCounts: Record<string, number>;
  artifactCount: number;
  updatedAt: string;
}
interface OrbitRunEnded {
  type: 'orbit/run-ended';
  sourcePosition: number;
  runId: string;
  revision: number;
  status: string;
  resultSummary?: string;
  errorSummary?: string;
  artifactCount: number;
  updatedAt: string;
}
type OrbitSessionEvent = OrbitRunStarted | OrbitRunCheckpoint | OrbitRunEnded;
//#endregion
export { AgentSummary, ArtifactContent, ArtifactSummary, AuthoringJob, AuthoringOutputChunk, AuthoringOutputPage, AuthoringSummary, EdgeSummary, GenerateAndRunOptions, GenerateAndRunResult, ImportedArtifact, IntegrationDiagnostics, OrbitCommandRequest, OrbitRunCheckpoint, OrbitRunEnded, OrbitRunStarted, OrbitSessionEvent, OutputChunk, OutputPage, RunDto, RunGraph, RuntimeEventHint, RuntimeEventPage, RuntimeSummary, StepSummary, WorkflowNode, WorkflowSummary, WorkspaceRef };