"""Run-local App bindings; published ports, edges and instructions stay intact."""

from dataclasses import replace

from ..agent_binding import AgentRebinding
from ..domain.definitions import IRHandlerRef
from ..domain.serialization import to_primitive
from .compiler import HandlerBindingError
from .harness_subagent import APP_DELEGATE_MANIFEST
from .project_access import project_access_need

# The isolation modes a delegation with `effects: write` is allowed to run
# under. `AppDelegationHandler.validate` and its Harness twin enforce the same
# pair at invoke time; naming it here is what lets the conflict be reported
# while the workflow is still being bound.
WRITE_ISOLATION_MODES = frozenset({"exclusive", "worktree"})


def validate_execution_mode(mode):
    if mode not in ("default", "current_app"):
        raise ValueError("execution_mode must be default or current_app")
    return mode


def bind_current_app(ir, registry):
    """Adapt the executor, keeping the graph's original data contract.

    `_agent_step` is internal snapshot metadata, not an authoring DSL option.
    The App adapter wraps these original inputs and instructions in a task at
    invocation time. Keeping ports avoids rewriting entry inputs, mappings,
    back edges and conditions merely to rename `prompt` to `task`.
    """
    manifest = APP_DELEGATE_MANIFEST
    reference = IRHandlerRef(manifest.name, manifest.fingerprint)
    project_need = project_access_need(ir)
    writing_nodes = (
        frozenset(project_need.agent_nodes) if project_need.write else frozenset()
    )
    nodes, rebound = [], {}
    for node in ir.nodes:
        is_agent = node.handler is not None and (
            node.handler.name.startswith("agent.")
            or node.handler.name in {"app.delegate", "harness.subagent"}
        )
        if node.handler is not None and not is_agent:
            try:
                is_agent = "agent.invoke" in registry.resolve(node).capabilities
            except HandlerBindingError:
                pass  # Normal compilation will report a missing non-Agent.
        if not is_agent:
            nodes.append(node)
            continue
        if node.kind != "action" or tuple(p.id for p in node.outputs) != ("result",):
            raise ValueError(f"current_app cannot adapt Agent node {node.id!r}: expected action with result output")
        for port in node.outputs:
            if port.data_policy.transport.value == "artifact_ref":
                # Every declared type, not the first one. `content_types` is
                # normalized to a *sorted set* — it says which types the port
                # accepts, in no order the author chose — so reading `[0]` as
                # "the primary type" both refused a markdown port that also
                # accepted PDF and admitted a JSON one that also accepted PNG.
                # The question is whether an App, which can produce prose or
                # JSON and nothing else, can satisfy this port at all.
                types = port.data_policy.content_types
                if not any(
                    item.startswith("text/") or item == "application/json"
                    for item in types
                ):
                    raise ValueError(f"current_app needs a text or JSON artifact output on node {node.id!r}")
        config = to_primitive(node.config)
        declared_isolation = config.get("isolation_mode")
        if node.handler.name == "app.delegate":
            config.update(target="run_initiator")
            config.pop("pool", None)
        else:
            timeout = config.get("timeout_seconds", config.get("max_wall_seconds", 1800))
            if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
                raise ValueError(f"invalid Agent timeout on node {node.id!r}")
            config = {
                "target": "run_initiator", "max_wall_seconds": min(timeout, 7200),
                "effects": config.get("effects", "read"),
                "isolation_mode": config.get("isolation_mode", "shared"),
                "_agent_step": {
                    "handler": to_primitive(node.handler),
                    "config": config,
                },
            }
        converted = replace(node, handler=reference, config=config)
        bound = registry.resolve(converted)  # Refuse before creating a Run if unavailable.
        if node.id in writing_nodes:
            # A workspace_access grant is run-wide: every Agent in the run is
            # handed the same writable directory, even when only one node
            # names the policy. Tell the App the truth about that capability
            # instead of leaving the Agent defaults at read/shared and making
            # the Host reject the delegation when it notices the task writes.
            config["effects"] = "write"
            if "workspace.project.write" in bound.capabilities:
                # The real checkout is protected by the Runtime's run-wide
                # occupancy claim, not by a disposable copy.
                required_isolation = "exclusive"
            elif "workspace.read" in bound.capabilities:
                required_isolation = "worktree"
            else:
                raise ValueError(
                    "current_app write delegation has no exclusive or "
                    "worktree project grant"
                )
            if declared_isolation is None or declared_isolation in WRITE_ISOLATION_MODES:
                # Corrected rather than refused. The mode describes the
                # workspace the Host receives, so calling a direct checkout
                # "worktree" would tell the App a different contract from the
                # path in its request — but which of the two a run gets is the
                # Runtime's grant to decide, not the definition's. Refusing the
                # other one would pin every published workflow that names this
                # field to one Runtime shape and fail it on the other, and the
                # library is durable: definitions outlive the Runtime they were
                # written on.
                config["isolation_mode"] = required_isolation
            else:
                # `shared` and `snapshot` cannot hold a write delegation at
                # all — the delegation Handler rejects that pair itself. Said
                # here, before a Run exists, because writing is not optional
                # for this node: the run's grant made it a write, so honouring
                # the declaration would build a node certain to fail its own
                # validation the moment it is invoked.
                raise ValueError(
                    f"node {node.id!r} declares isolation_mode "
                    f"{declared_isolation!r}, which cannot hold a write "
                    f"delegation; this run's workspace_access policy makes it "
                    f"one. Declare {required_isolation!r} or leave "
                    f"isolation_mode out."
                )
            converted = replace(node, handler=reference, config=config)
        nodes.append(converted)
        rebound[node.id] = reference
    return AgentRebinding(replace(ir, nodes=tuple(nodes)), rebound)
