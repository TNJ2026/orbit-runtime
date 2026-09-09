/** Teaching the Harness's Session store about Orbit's own events.
 *
 * A module augmentation names a package, so it can only live where that
 * package is a dependency. The shapes it refers to are host-agnostic and now
 * live in the shared core; this file is the one line of the pair that is about
 * DeepSeek-Harness, and it stays here for that reason alone.
 */

import type {
  OrbitRunStarted, OrbitRunCheckpoint, OrbitRunEnded,
} from '@promptaflow/integration-core'

declare module '@deepseek-ai/dsh-session/types' {
  interface SessionEventMap {
    'promptaflow/run-started': Omit<OrbitRunStarted, 'type'>
    'promptaflow/run-checkpoint': Omit<OrbitRunCheckpoint, 'type'>
    'promptaflow/run-ended': Omit<OrbitRunEnded, 'type'>
    // Written by every build before the rename, and still in the Session logs
    // those builds produced. Declared so reading one is typed, never written.
    'orbit/run-started': Omit<OrbitRunStarted, 'type'>
    'orbit/run-checkpoint': Omit<OrbitRunCheckpoint, 'type'>
    'orbit/run-ended': Omit<OrbitRunEnded, 'type'>
  }
}
