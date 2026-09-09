/**
 * `/promptaflow` opens PromptaFlow's own Runtime UI inside the Harness window.
 *
 * The panel holds an iframe and nothing else. Every earlier version of this
 * module drew PromptaFlow's data itself — a Run drawer, a Workflow picker, a
 * settings page — and each was a second account of something PromptaFlow already
 * renders. Showing PromptaFlow's own page instead means there is one interface, and
 * this module's whole job is deciding when it is visible.
 *
 * @module @promptaflow/dsh/client
 */
import type { ClientContext } from '@deepseek-ai/dsh-client-runtime/client';
export declare function registerPromptaFlowSlashSource(ctx: ClientContext): void;
export declare const inject: string[];
export declare function apply(ctx: ClientContext): void;
