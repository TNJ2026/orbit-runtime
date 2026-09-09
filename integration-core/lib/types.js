/**
 * Event types this bridge recognises when it reads a Session back.
 *
 * A Session log written before the rename is durable data in the user's own
 * store: the `orbit/` spellings are never written again, and must never stop
 * being read, or a resumed Session loses every Run it already knew about.
 */
export const RUN_EVENT_TYPES = [
    'promptaflow/run-started', 'promptaflow/run-checkpoint', 'promptaflow/run-ended',
    'orbit/run-started', 'orbit/run-checkpoint', 'orbit/run-ended',
];
