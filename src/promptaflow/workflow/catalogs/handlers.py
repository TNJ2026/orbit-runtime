"""Read-only Handler Catalog port and deterministic in-memory adapter."""

from __future__ import annotations

from dataclasses import dataclass, fields as fields_of
import hashlib
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol

from ..domain.durable_execution import ExecutionSafety
from ..domain.handlers import ResourceProfile
from ..domain.serialization import canonical_json, freeze_json, to_primitive


_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ValueError(f"handler version must be semantic x.y.z: {value!r}")
    return tuple(int(item) for item in match.groups())  # type: ignore[return-value]


def _matches(version: str, constraint: str) -> bool:
    candidate = _version_tuple(version)
    if constraint.startswith("^"):
        parts = constraint[1:].split(".")
        if len(parts) not in {1, 2, 3} or not all(part.isdigit() for part in parts):
            raise ValueError(f"unsupported handler version constraint: {constraint!r}")
        requested = tuple(int(item) for item in parts)
        lower = requested + (0,) * (3 - len(requested))
        if candidate < lower:
            return False
        if lower[0] > 0:
            return candidate < (lower[0] + 1, 0, 0)
        if len(requested) >= 2:
            return candidate < (0, lower[1] + 1, 0)
        return candidate < (1, 0, 0)
    return version == constraint


@dataclass(frozen=True)
class HandlerManifest:
    name: str
    version: str
    node_kinds: tuple[str, ...]
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    config_schema: Mapping[str, object]
    execution_safety: ExecutionSafety
    resource_profile: ResourceProfile
    result_schema_id: str
    capabilities: tuple[str, ...] = ()
    required_secrets: tuple[str, ...] = ()
    supports_cancel: bool = False
    supports_recover: bool = False
    manifest_version: str = "1.0"
    # Older contract fingerprints this implementation remains able to honour.
    # This is migration metadata, not part of the current contract itself.
    compatible_fingerprints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("handler name is required")
        _version_tuple(self.version)
        if self.manifest_version != "1.0":
            raise ValueError("unsupported Handler Execution Manifest version")
        if not self.node_kinds:
            raise ValueError("handler must support at least one node kind")
        if not self.result_schema_id.strip():
            raise ValueError("result_schema_id is required")
        object.__setattr__(self, "node_kinds", tuple(sorted(set(self.node_kinds))))
        object.__setattr__(self, "inputs", MappingProxyType(dict(sorted(self.inputs.items()))))
        object.__setattr__(self, "outputs", MappingProxyType(dict(sorted(self.outputs.items()))))
        object.__setattr__(self, "config_schema", freeze_json(self.config_schema))
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))
        object.__setattr__(self, "required_secrets", tuple(sorted(set(self.required_secrets))))
        object.__setattr__(
            self, "compatible_fingerprints",
            tuple(sorted(set(self.compatible_fingerprints))),
        )
        for value in (*self.capabilities, *self.required_secrets):
            if not value.strip():
                raise ValueError("capability and secret names cannot be empty")
        for value in self.compatible_fingerprints:
            if not value.startswith("sha256:"):
                raise ValueError("compatible handler fingerprint must be sha256")

    def __reduce__(self):
        """Carry this manifest to a worker process that cannot fork.

        `__post_init__` freezes `inputs`, `outputs` and `config_schema` into
        `MappingProxyType`, which pickle refuses — and the registrations are
        pickled whenever `multiprocessing` uses `spawn` rather than `fork`.
        That is every Windows Runtime: `--execution-workers` defaults to 1, so
        `orbit serve` died in `process.start()` before it ever bound a port.

        Rebuilt through the constructor rather than by restoring attributes,
        so the manifest arriving in the worker is re-frozen and re-validated
        exactly like one built there — a fingerprint computed on either side
        of the pipe has to agree, because that is what a published Workflow's
        binding was resolved against.
        """

        values = {field.name: getattr(self, field.name) for field in fields_of(self)}
        values["inputs"] = dict(self.inputs)
        values["outputs"] = dict(self.outputs)
        # Nested, and the only field holding arbitrary JSON. `to_primitive` is
        # deliberately not applied to the whole manifest: it would flatten
        # `execution_safety` and `resource_profile` into bare strings.
        values["config_schema"] = to_primitive(self.config_schema)
        return (_rebuild_manifest, (values,))

    @property
    def fingerprint(self) -> str:
        """The contract this Handler promises, without its build number.

        A CLI release is an operational upgrade, not a contract migration. What
        a binding has to be sure of is the ports, schemas and capabilities a
        Workflow was compiled against — the version is none of those. While it
        was hashed in here, every routine upgrade produced a different
        fingerprint, so a published Workflow naming the build it was written
        against stopped resolving the moment that build was replaced.
        """

        payload = {
            key: value for key, value in to_primitive(self).items()
            if key not in {"version", "compatible_fingerprints"}
        }
        return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()

    @property
    def legacy_fingerprint(self) -> str:
        """What `fingerprint` was while the build number was still in it.

        Published WorkflowVersions are immutable — a database trigger enforces
        it — so fingerprints already recorded in them can never be rewritten.
        They are accepted at resolve time instead: a Workflow published before
        this change keeps running on the exact build it named, and anything
        compiled after it survives an upgrade. Both are the same Handler; only
        one of them says so in a way that outlives a release.
        """

        payload = {
            key: value for key, value in to_primitive(self).items()
            if key != "compatible_fingerprints"
        }
        return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _rebuild_manifest(values: dict[str, Any]) -> HandlerManifest:
    """Reconstruct a pickled manifest through its validating constructor."""

    return HandlerManifest(**values)


class HandlerCatalog(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def resolve(self, name: str) -> HandlerManifest | None: ...


class InMemoryHandlerCatalog:
    def __init__(self, manifests: Iterable[HandlerManifest]) -> None:
        by_name: dict[str, list[HandlerManifest]] = {}
        seen: set[str] = set()
        for manifest in manifests:
            key = manifest.name
            if key in seen:
                raise ValueError(f"duplicate handler manifest: {manifest.name}@{manifest.version}")
            seen.add(key)
            by_name.setdefault(manifest.name, []).append(manifest)
        self._by_name = {
            name: tuple(values)
            for name, values in by_name.items()
        }
        payload = [
            manifest
            for name in sorted(self._by_name)
            for manifest in reversed(self._by_name[name])
        ]
        self._fingerprint = "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def resolve(self, name: str) -> HandlerManifest | None:
        """Resolve one registered implementation by name."""
        candidates = self._by_name.get(name, ())
        return candidates[0] if candidates else None
