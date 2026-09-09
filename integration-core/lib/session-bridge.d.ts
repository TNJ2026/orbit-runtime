import type { PromptaFlowSessionEvent, WorkspaceRef } from './types.js';
import { PromptaFlowGateway } from './gateway.js';
export interface PromptaFlowEventSink {
    append(event: PromptaFlowSessionEvent): void | Promise<void>;
}
export interface PromptaFlowCursorStore {
    load(workspaceId: string, sessionId: string): number | undefined | Promise<number | undefined>;
    save(workspaceId: string, sessionId: string, position: number): void | Promise<void>;
}
export interface StoredPromptaFlowEvent {
    type: string;
    data: unknown;
}
export declare function restoredBridgeState(events: readonly StoredPromptaFlowEvent[]): {
    position: number;
    knownRuns: Set<string>;
};
export declare function sessionCanBridge(header: {
    cwd?: string;
    delegationDepth?: number;
}): boolean;
export interface BridgeRetryOptions {
    /**
     * The Session's durable events, read afresh for every attempt.
     *
     * Never hoist this into a value. A Run an earlier attempt already announced
     * is durably recorded here, and that record is the only thing standing
     * between a transient failure and a second announcement of the same Run.
     */
    events: () => readonly StoredPromptaFlowEvent[];
    attempt: (knownRuns: Set<string>) => Promise<void>;
    onWaiting: (message: string) => void;
    signal: AbortSignal;
    retryDelayMs?: number;
}
export declare function bridgeDelay(ms: number, signal: AbortSignal): Promise<void>;
/** Keep attempting a Session Bridge until it finishes or the caller gives up. */
export declare function bridgeWithRetry(options: BridgeRetryOptions): Promise<void>;
export declare class PromptaFlowSessionBridge {
    private readonly gateway;
    private readonly cursor;
    private readonly intervalMs;
    constructor(gateway: PromptaFlowGateway, cursor: PromptaFlowCursorStore, intervalMs?: number);
    run(workspace: WorkspaceRef, sessionId: string, sink: PromptaFlowEventSink, signal: AbortSignal, knownRuns?: Iterable<string>): Promise<void>;
}
//# sourceMappingURL=session-bridge.d.ts.map