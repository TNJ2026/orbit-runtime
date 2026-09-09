/** Teaching the Harness's Session store about PromptaFlow's own events.
 *
 * A module augmentation names a package, so it can only live where that
 * package is a dependency. The shapes it refers to are host-agnostic and now
 * live in the shared core; this file is the one line of the pair that is about
 * DeepSeek-Harness, and it stays here for that reason alone.
 */

import type {
  PromptaFlowRunStarted, PromptaFlowRunCheckpoint, PromptaFlowRunEnded,
} from '@promptaflow/integration-core'

declare module '@deepseek-ai/dsh-session/types' {
  interface SessionEventMap {
    'promptaflow/run-started': Omit<PromptaFlowRunStarted, 'type'>
    'promptaflow/run-checkpoint': Omit<PromptaFlowRunCheckpoint, 'type'>
    'promptaflow/run-ended': Omit<PromptaFlowRunEnded, 'type'>
  }
}
