"""A constrained, reviewable proposal to trust one more Agent CLI.

The allowlist in `agent_discovery` grows one way: somebody edits that file and
somebody reviews the edit. This module exists so the tedious half of that —
working out whether a program is even here, and what it calls itself — can be
done for them, without the answer ever becoming an executable on its own.

The output is a tightly scoped patch. The candidate's help text is checked for
one of PromptaFlow's code-owned maximum-permission profiles. Known, previously
exercised invocation profiles receive that profile automatically; unknown CLIs
remain detection-only until their prompt transport receives a code review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import difflib
import os
from pathlib import Path
from typing import Callable, Sequence
import shutil
import subprocess

from .agent_discovery import (
    TRUSTED_AGENT_CLIS, AgentCliSpec, AgentInvocation, CandidateProbe,
    probe_executable,
)
from ...environment import env


DISCOVERY_FILE = "src/promptaflow/workflow/catalogs/agent_discovery.py"
DISCOVERY_TESTS = "tests/test_agent_discovery.py"

# Where each edit goes. Anchored on text rather than line numbers so a patch is
# either correct or refused outright: a moved anchor raises here instead of
# producing a diff that applies to the wrong place.
_ALLOWLIST_END = "\n)\n\n\n@dataclass(frozen=True)\nclass DiscoveredAgent:"
_REVIEWED_SET_END = (
    "            },\n            {(spec.name, spec.executable) for spec in TRUSTED_AGENT_CLIS},"
)
_PERMISSIONS_END = "            },\n            settings,\n        )"


def source_checkout_root(configured: Path | str | None = None) -> Path | None:
    """Return the PromptaFlow checkout that may receive a generated proposal patch.

    A Workspace Runtime runs with the user's project as its cwd.  That project
    is the *target* of workflows, never the checkout containing PromptaFlow's trusted
    Agent allowlist.  Repository launchers therefore name their own checkout
    through ``PROMPTAFLOW_SOURCE_ROOT``; editable development installs can derive the
    same root from this module.  A wheel installation has neither and must not
    pretend that its site-packages directory is an editable source tree.
    """

    explicit = configured
    if explicit is None:
        explicit = env("SOURCE_ROOT")
    candidates = (
        (Path(explicit).expanduser(),)
        if explicit
        else (Path(__file__).resolve().parents[4],)
    )
    required = (DISCOVERY_FILE, DISCOVERY_TESTS)
    for candidate in candidates:
        try:
            root = candidate.resolve()
        except OSError:
            continue
        if all((root / relative).is_file() for relative in required):
            return root
    return None


# Invocation profiles that were already exercised against the named CLI.
# Unknown CLIs remain detection-only until somebody reviews their invocation.
_REVIEWED_INVOCATIONS: dict[str, AgentInvocation] = {
    "kimi": AgentInvocation(prompt_flag="-p"),
}


@dataclass(frozen=True)
class AgentProposal:
    """One candidate, with the verdict a reviewer needs and why."""

    probe: CandidateProbe
    verdict: str
    detail: str

    @property
    def proposable(self) -> bool:
        return self.verdict == "proposable"


def propose(
    names: Sequence[str],
    *,
    specs: Sequence[AgentCliSpec] = TRUSTED_AGENT_CLIS,
    which: Callable[[str], str | None] = shutil.which,
    runner=subprocess.run,
) -> tuple[AgentProposal, ...]:
    """Judge each proposed program name, in the order it was suggested.

    Duplicates collapse: a suggestion list is somebody's guesses, and guessing
    the same thing twice is not two candidates.
    """

    seen: set[str] = set()
    out: list[AgentProposal] = []
    for name in names:
        probe = probe_executable(name, specs=specs, which=which, runner=runner)
        if probe.executable in seen:
            continue
        seen.add(probe.executable)
        out.append(AgentProposal(probe, *_judge(probe)))
    return tuple(out)


def _judge(probe: CandidateProbe) -> tuple[str, str]:
    if probe.refused is not None:
        return "refused", probe.refused
    if probe.already_trusted is not None:
        return (
            "already_trusted",
            f"the allowlist already covers this program as {probe.already_trusted!r}",
        )
    if not probe.on_path:
        return "not_installed", "nothing by this name resolves on PATH"
    if probe.version is None:
        # Detection and registration are separate facts, and this is where they
        # part: `agent_discovery` will list a CLI whose version it could not
        # establish, but registering one would put a version in a manifest
        # fingerprint that nothing ever confirmed.
        return (
            "unpinned",
            "it is installed, but its version flag produced no version — "
            "an unpinned build cannot be registered",
        )
    permission_detail = (
        "maximum-permission arguments detected: " + " ".join(probe.permission_args)
        if probe.permission_args else
        "help checked; no reviewed maximum-permission argument was advertised"
        if probe.help_checked else
        "help could not be checked; no permission argument will be assumed"
    )
    return (
        "proposable",
        f"installed and reporting version {probe.version}; {permission_detail}",
    )


def _reviewed_invocation(proposal: AgentProposal) -> AgentInvocation | None:
    """Merge detected permissions only into a known prompt transport."""

    invocation = _REVIEWED_INVOCATIONS.get(proposal.probe.executable)
    if invocation is None:
        return None
    args = tuple(dict.fromkeys((*invocation.args, *proposal.probe.permission_args)))
    return replace(invocation, args=args)


def _render_invocation(invocation: AgentInvocation) -> str:
    fields = []
    if invocation.args:
        fields.append(f"args={invocation.args!r}")
    if invocation.prompt_flag is not None:
        fields.append(f"prompt_flag={invocation.prompt_flag!r}")
    if invocation.prompt_positional:
        fields.append("prompt_positional=True")
    if invocation.process_timeout_flag is not None:
        fields.append(f"process_timeout_flag={invocation.process_timeout_flag!r}")
    return "invocation=AgentInvocation(" + ", ".join(fields) + ")"


def render_patch(
    proposals: Sequence[AgentProposal], *, root: Path | str = Path("."),
) -> str:
    """A unified diff adding every proposable candidate, or "" when none are.

    Both pinned tests are edited alongside the allowlist, because leaving them
    to fail would teach whoever hits it that those assertions are chores to
    update rather than the review gate they are.
    """

    additions = [item for item in proposals if item.proposable]
    if not additions:
        return ""

    root = Path(root)
    specs = ""
    for item in additions:
        invocation = _reviewed_invocation(item)
        permission_note = (
            " ".join(item.probe.permission_args) if item.probe.permission_args
            else "none advertised"
        )
        specs += (
            f"    # Proposed from system probes: version {item.probe.version};\n"
            f"    # maximum-permission arguments: {permission_note}.\n"
            f'    AgentCliSpec("{item.probe.executable}", "{item.probe.executable}"'
            f'{", " + _render_invocation(invocation) if invocation else ""}),\n'
        )
    reviewed = "".join(
        f'                ("{item.probe.executable}", "{item.probe.executable}"),\n'
        for item in additions
    )
    permissions = ""
    for item in additions:
        invocation = _reviewed_invocation(item)
        applied = item.probe.permission_args if invocation is not None else ()
        reason = (
            "Detected and applied to the reviewed invocation."
            if applied else
            "Detected, but no reviewed prompt transport exists yet."
            if item.probe.permission_args else
            "No reviewed maximum-permission argument was advertised."
        )
        permissions += (
            f"                # {reason}\n"
            f'                "{item.probe.executable}": {applied!r},\n'
        )

    return "".join([
        _edit(root, DISCOVERY_FILE, _ALLOWLIST_END,
              _ALLOWLIST_END.replace("\n)", "\n" + specs + ")", 1)),
        _edit(root, DISCOVERY_TESTS, _REVIEWED_SET_END,
              _REVIEWED_SET_END.replace("            },", reviewed + "            },", 1)),
        _edit(root, DISCOVERY_TESTS, _PERMISSIONS_END,
              _PERMISSIONS_END.replace("            },", permissions + "            },", 1)),
    ])


def apply_patch(patch: str, *, root: Path | str = Path(".")) -> None:
    """Apply only a patch produced by :func:`render_patch` to this checkout."""

    if not patch.strip():
        return
    root = Path(root).resolve()
    expected = {DISCOVERY_FILE, DISCOVERY_TESTS}
    touched = {
        line[6:] for line in patch.splitlines()
        if line.startswith("+++ b/")
    }
    if touched != expected:
        raise ValueError("agent proposal patch targets unexpected files")
    checked = subprocess.run(
        ["git", "apply", "--check", "-"], cwd=root, input=patch,
        text=True, capture_output=True,
    )
    if checked.returncode != 0:
        raise ValueError(checked.stderr.strip() or "agent proposal patch no longer applies")
    applied = subprocess.run(
        ["git", "apply", "-"], cwd=root, input=patch,
        text=True, capture_output=True,
    )
    if applied.returncode != 0:
        raise ValueError(applied.stderr.strip() or "could not apply agent proposal patch")


def _edit(root: Path, relative: str, anchor: str, replacement: str) -> str:
    path = root / relative
    before = path.read_text(encoding="utf-8")
    if before.count(anchor) != 1:
        raise ValueError(
            f"{relative}: expected exactly one anchor, found {before.count(anchor)}"
        )
    after = before.replace(anchor, replacement)
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{relative}", tofile=f"b/{relative}", n=3,
    ))
