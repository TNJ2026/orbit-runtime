import type { Context } from '@deepseek-ai/cordis';
import { PromptaFlowGateway } from '@promptaflow/integration-core';
import type { AuthoringJob, WorkspaceRef } from '@promptaflow/integration-core';
/** Told when an authoring job starts here, so the panel can show it running. */
export type AuthoringWatcher = (workspace: WorkspaceRef, sessionId: string, job: AuthoringJob) => void;
export declare class PromptaFlowToolBridge {
    private readonly ctx;
    private readonly gateway;
    private readonly watch;
    private readonly tools;
    private readonly registry;
    constructor(ctx: Context, gateway: PromptaFlowGateway, watch?: AuthoringWatcher);
    register(): void;
    private definitions;
    private definition;
    private command;
    private call;
    private route;
}
