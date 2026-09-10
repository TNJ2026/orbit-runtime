# Run file deliverables

Prompt CLI replies and generated files are different outputs. The existing
`result` port still carries exactly the declared inline object or text Artifact.
The trusted CLI adapter additionally publishes explicitly linked local files as
run-scoped attachments (`port_id: attachment:<relative-path>`). They use the same
owner, attempt, staging/commit lifecycle, CAS storage and authenticated download
endpoint as other Artifacts; they do not widen any declared port's MIME policy.

Agents should link each intended deliverable in their final Markdown response.
The collector does not scan cwd, recurse into directories, fetch URLs, or chase
links inside documents. Supported document/image extensions are enumerated in
`workflow/handlers/deliverables.py`. Limits are 64 files, 64 MiB per file and
128 MiB per batch. Files are read beneath the actual granted CLI cwd using
directory-relative, no-follow opens; hidden paths, traversal, symlinks and
non-regular files are rejected. Platforms without safe no-follow opens report
publication as unavailable. Runtime secret-value checks apply before staging.
A missing/unsafe linked file reports a publication warning in the reply rather
than pretending delivery succeeded or re-running completed external actions.

For historical completed runs, an operator can explicitly select workspace
files with `publish_run_files` (MCP) or the run's `publish-files` HTTP command.
Read `allowed_commands` first. The operation requires ops-write permission,
ownership visibility, a project grant, expected revision and an idempotency key.
It preserves the run result and attempts, records `artifacts_published`, and
atomically publishes the staged metadata with its receipt. The timestamp is the
metadata update time, not an additional execution. Selected historical files are
their current bytes: callers must verify they still belong to that run.

The full UI lists attachments before textual results and supports authenticated
downloads. MCP run/current-task cards list file names and send an open-file
request back to the host conversation. MCP App resource URIs are versioned;
already-mounted cached cards require reopening after the Gateway is updated.
