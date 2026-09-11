from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

from promptaflow.hub import (
    HubError, MultipleRuntimesError, ProjectAccessGrants, WorkspaceRegistry,
    WorkspaceRuntimeManager, create_hub_app, workspace_urls,
)
from promptaflow.global_control import WorkflowTemplateStore
from promptaflow.platform.projects import project_id
from promptaflow.platform.runtime_ownership import DiscoveredRuntime
from tests.test_web_composition import AsgiHarness


class WorkspaceRegistryTests(unittest.TestCase):
    def test_production_manifest_uses_the_fixed_global_hub(self) -> None:
        manifest = json.loads(
            (Path(__file__).resolve().parents[1] / "agent-app.json").read_text()
        )

        self.assertEqual("global", manifest["scope"])
        self.assertEqual(
            ["{manifest_dir}/start-promptaflow.sh", "--hub-service"],
            manifest["service"]["command"],
        )
        self.assertIn("PROMPTAFLOW_CLI", manifest["service"]["environment"])
        self.assertEqual("http://127.0.0.1:8848/health/ready", manifest["service"]["ready_url"])
        self.assertEqual("http://127.0.0.1:8848/mcp", manifest["mcp"]["url"])

    def test_registration_is_stable_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, resolved = registry.register(workspace)

            self.assertEqual(project_id(workspace), identifier)
            self.assertEqual(workspace.resolve(), resolved)
            self.assertEqual(workspace.resolve(), WorkspaceRegistry(registry.path).resolve(identifier))

    def test_a_registration_can_be_taken_back(self) -> None:
        """Registering made a directory routable; nothing was ever the reverse.

        So a directory opened once stayed in the list for good, and a suite
        that opens a throwaway directory per run added one every time.
        """

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, _ = registry.register(workspace)

            self.assertTrue(registry.forget(identifier))
            self.assertNotIn(
                identifier,
                {item["workspace_id"] for item in registry.list()},
            )
            self.assertTrue(workspace.is_dir(), "forgetting is not deleting")
            self.assertFalse(registry.forget(identifier), "and it is idempotent")

    def test_prune_takes_only_what_is_gone_and_unserved(self) -> None:
        """Offline is not the same as gone, and a live Runtime outranks a stat."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = WorkspaceRegistry(root / "workspaces.json")
            kept, removed, served = (root / name for name in ("kept", "removed", "served"))
            for directory in (kept, removed, served):
                directory.mkdir()
            ids = {
                name: registry.register(directory)[0]
                for name, directory in (
                    ("kept", kept), ("removed", removed), ("served", served),
                )
            }
            shutil.rmtree(removed)
            shutil.rmtree(served)

            forgotten = registry.prune(live={ids["served"]})

            self.assertEqual([ids["removed"]], forgotten)
            remaining = {item["workspace_id"] for item in registry.list()}
            self.assertIn(ids["kept"], remaining, "offline is not gone")
            self.assertIn(ids["served"], remaining, "a Runtime answers for it")
            self.assertNotIn(ids["removed"], remaining)

    def test_the_registry_can_be_pointed_somewhere_else(self) -> None:
        """Registering runs through the CLI, so only an env var can redirect it.

        Without that a test suite writes its throwaway directories into the
        developer's own registry, which is how twenty-four of them got there.
        """

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(os.environ, {"PROMPTAFLOW_HUB_ROOT": str(root)}):
                self.assertEqual(root / "workspaces.json", WorkspaceRegistry().path)
            self.assertNotEqual(root / "workspaces.json", WorkspaceRegistry().path)

    def test_default_workspace_is_created_on_first_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = root / "default"
            registry = WorkspaceRegistry(root / "workspaces.json")
            with mock.patch.dict(
                "os.environ", {"PROMPTAFLOW_DEFAULT_WORKSPACE": str(default)}, clear=False,
            ):
                self.assertEqual(default.resolve(), registry.resolve(None))
            self.assertTrue(default.is_dir())

    def test_explicit_registration_does_not_create_a_misspelled_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "misspelled" / "project"
            registry = WorkspaceRegistry(Path(temporary) / "workspaces.json")

            with self.assertRaisesRegex(HubError, "not an existing directory"):
                registry.register(missing)

            self.assertFalse(missing.exists())

    def test_a_deleted_workspace_stays_registered_but_is_not_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, _ = registry.register(workspace)
            workspace.rmdir()

            with mock.patch.dict(
                "os.environ", {"PROMPTAFLOW_DEFAULT_WORKSPACE": str(root / "default")},
                clear=False,
            ):
                listed = next(
                    item for item in registry.list()
                    if item["workspace_id"] == identifier
                )
                self.assertFalse(listed["available"])
                with self.assertRaisesRegex(HubError, "workspace is unavailable"):
                    registry.select(name="project")

            self.assertEqual(str(workspace.resolve()), listed["path"])
            with self.assertRaisesRegex(HubError, "workspace is unavailable"):
                registry.resolve(identifier)

    def test_workspace_urls_are_namespaced(self) -> None:
        self.assertEqual(
            {
                "workspace_id": "abc",
                "mcp_url": "http://127.0.0.1:8848/workspaces/abc/mcp",
                "ui_url": "http://127.0.0.1:8848/workspaces/abc/ui/",
                "events_url": "ws://127.0.0.1:8848/workspaces/abc/events",
            },
            workspace_urls("abc"),
        )


class ProjectAccessGrantTests(unittest.TestCase):
    """The one route an operator's consent has into a Hub-started Runtime.

    The persisted Hub grant decides whether a `workspace_access` policy can be
    satisfied at all, and the Hub writes the whole argv of every
    Runtime it launches. Until this, the switch was unreachable through the
    ordinary way of starting PromptaFlow, and a workflow declaring the policy was
    refused on a Runtime that could never have been started to allow it.
    """

    def manager(self, root: Path, grants: ProjectAccessGrants):
        registry = WorkspaceRegistry(root / "workspaces.json")
        (root / "project").mkdir(exist_ok=True)
        identifier, workspace = registry.register(root / "project")
        return identifier, workspace, WorkspaceRuntimeManager(
            registry=registry, grants=grants, runtime_discovery=lambda: (),
            health_check=lambda _url: True, launcher=lambda _path: None,
        )

    def test_a_workspace_without_the_grant_is_started_without_the_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            _identifier, workspace, manager = self.manager(root, grants)

            arguments = manager._serve_arguments(workspace)

            self.assertNotIn("--agent-project-access", arguments)
            self.assertIn("_runtime", arguments)
            self.assertIn("--project-root", arguments)

    def test_a_granted_workspace_carries_the_switch_into_its_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            identifier, workspace, manager = self.manager(root, grants)
            grants.set(identifier, allowed=True)

            self.assertIn("--agent-project-access", manager._serve_arguments(workspace))

    def test_a_legacy_boolean_grant_is_not_consent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "project-access.json"
            identifier, workspace, manager = self.manager(
                root, ProjectAccessGrants(path),
            )
            path.write_text(json.dumps({"project_access": {identifier: True}}))

            arguments = manager._serve_arguments(workspace)
            self.assertNotIn("--agent-project-access", arguments)
            self.assertFalse(ProjectAccessGrants(path).granted(identifier))

    def test_the_grant_is_taken_back_by_asking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            identifier, workspace, manager = self.manager(root, grants)
            grants.set(identifier, allowed=True)
            grants.set(identifier, allowed=False)

            self.assertFalse(grants.granted(identifier))
            self.assertNotIn(
                "--agent-project-access", manager._serve_arguments(workspace)
            )

    def test_default_enable_does_not_override_an_explicit_disable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            identifier, workspace, manager = self.manager(root, grants)
            grants.set(identifier, allowed=False)
            grants.enable_by_default(identifier)

            self.assertEqual("disabled", grants.mode(identifier))
            self.assertFalse(grants.granted(identifier))
            self.assertNotIn(
                "--agent-project-access", manager._serve_arguments(workspace)
            )

    def test_configured_default_workspace_always_has_full_project_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            identifier, workspace, manager = self.manager(root, grants)
            grants.set(identifier, allowed=False)

            with mock.patch.dict(
                os.environ,
                {"PROMPTAFLOW_DEFAULT_WORKSPACE": str(workspace)},
                clear=False,
            ):
                self.assertEqual("read_write", grants.mode(identifier))
                self.assertTrue(grants.granted(identifier))
                self.assertIn(
                    "--agent-project-access", manager._serve_arguments(workspace)
                )

    def test_the_grant_survives_a_re_registration(self) -> None:
        """Registering happens on every start; permission must not ride on it.

        `start-promptaflow.sh` runs `hub register` each time, and the Workspace
        registry is rewritten by it. A grant kept in that file would be
        revoked by the next ordinary start, silently.
        """

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            grants = ProjectAccessGrants(root / "project-access.json")
            identifier, _workspace, _manager = self.manager(root, grants)
            grants.set(identifier, allowed=True)

            registry = WorkspaceRegistry(root / "workspaces.json")
            registry.register(root / "project")

            self.assertTrue(
                ProjectAccessGrants(root / "project-access.json").granted(identifier)
            )

    def test_only_known_persisted_grant_shapes_are_consent(self) -> None:

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "project-access.json"
            path.write_text(json.dumps({"project_access": {
                "legacy": True, "read": "legacy_read", "write": "read_write",
                "truthy": 1, "worded": "true", "off": False,
            }}), encoding="utf-8")
            grants = ProjectAccessGrants(path)

            self.assertEqual("read_write", grants.mode("write"))
            for identifier in (
                "legacy", "read", "truthy", "worded", "off", "absent",
            ):
                with self.subTest(identifier=identifier):
                    self.assertFalse(grants.granted(identifier))

    def test_a_damaged_file_grants_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "project-access.json"
            path.write_text("{not json", encoding="utf-8")

            self.assertFalse(ProjectAccessGrants(path).granted("anything"))

    def test_the_cli_records_the_decision_and_reports_it_every_time(self) -> None:
        """Through the entry point an operator actually types.

        Reported on every registration rather than only when it changes:
        `hub register` is what `start-promptaflow.sh` runs, so it is the one moment
        the person opening a Workspace is told whether a workflow in it can
        read the project.
        """

        import subprocess
        import sys

        repository = Path(__file__).resolve().parents[1]

        def register(*flags: str) -> dict:
            result = subprocess.run(
                [sys.executable, "-m", "promptaflow", "hub", "register",
                 str(workspace), *flags],
                capture_output=True, text=True, timeout=120,
                env={
                    # Inherit Windows' process bootstrap variables, especially
                    # SystemRoot: asyncio cannot initialise Winsock without it.
                    # The executable is explicit, so the test does not need to
                    # replace PATH with a POSIX-only value for isolation.
                    **os.environ,
                    "PYTHONPATH": str(repository / "src"),
                    "PROMPTAFLOW_HUB_ROOT": str(hub_root),
                },
            )
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hub_root = root / "hub"
            workspace = root / "project"
            workspace.mkdir()

            plain = register()
            granted = register("--agent-project-access")
            # The ordinary start that happens every time: it must not be a
            # silent revocation.
            again = register()
            revoked = register("--no-agent-project-access")
            still_revoked = register()

            self.assertTrue(plain["agent_project_access"])
            self.assertTrue(granted["agent_project_access"])
            self.assertTrue(again["agent_project_access"])
            self.assertFalse(revoked["agent_project_access"])
            self.assertFalse(still_revoked["agent_project_access"])
            self.assertEqual("disabled", revoked["agent_project_access_mode"])
            self.assertEqual("read_write", granted["agent_project_access_mode"])
            self.assertEqual(
                "non_git_direct_read_write_no_rollback",
                granted["effective_project_access"],
            )
            self.assertEqual(str(workspace.resolve()), plain["workspace_path"])
            self.assertEqual(plain["workspace_id"], granted["workspace_id"])


class WorkspaceRuntimeManagerTests(unittest.TestCase):
    @mock.patch("promptaflow.hub.subprocess.Popen")
    def test_default_launcher_gives_the_runtime_a_unique_owner_token(
        self, popen,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            process = popen.return_value
            manager = WorkspaceRuntimeManager(log_root=root / "logs")

            launched = manager._launch(workspace)  # noqa: SLF001

            arguments = popen.call_args.args[0]
            token_index = arguments.index("--hub-owner-token") + 1
            token = arguments[token_index]
            self.assertRegex(token, r"^[0-9a-f]{32}$")
            self.assertEqual(token, launched._promptaflow_owner_token)

    def test_crashed_hub_releases_kernel_lock_for_successor(self):
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "launched-runtimes.json"
            result = subprocess.run([
                sys.executable, "-c",
                "import os, sys; from promptaflow.hub import WorkspaceRuntimeManager; "
                "manager = WorkspaceRuntimeManager(ownership_path=sys.argv[1]); os._exit(0)",
                str(record),
            ], capture_output=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            successor = WorkspaceRuntimeManager(ownership_path=record)
            successor.close()

    def test_live_hub_excludes_successor_until_ownership_is_released(self):
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "launched-runtimes.json"
            first = WorkspaceRuntimeManager(ownership_path=record)
            try:
                with self.assertRaises(HubError):
                    WorkspaceRuntimeManager(ownership_path=record)
            finally:
                first.close()
            successor = WorkspaceRuntimeManager(ownership_path=record)
            successor.close()

    def test_concurrent_snapshots_preserve_all_owned_runtimes(self):
        from promptaflow.hub import _OwnedRuntime

        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "launched-runtimes.json"
            manager = WorkspaceRuntimeManager(ownership_path=record)
            entered, proceed = threading.Event(), threading.Event()
            original = Path.write_text
            errors = []

            def paused_write(path, *args, **kwargs):
                if threading.current_thread().name == "first-write":
                    entered.set()
                    if not proceed.wait(3):
                        raise AssertionError("writer was not released")
                return original(path, *args, **kwargs)

            def persist_second():
                try:
                    with manager._guard:
                        manager._owned_runtimes[22] = _OwnedRuntime("b", "/b")
                    manager._persist_owned()
                except Exception as exc:
                    errors.append(exc)

            manager._owned_runtimes[11] = _OwnedRuntime("a", "/a")
            try:
                with patch.object(Path, "write_text", paused_write):
                    first = threading.Thread(target=manager._persist_owned, name="first-write")
                    first.start()
                    self.assertTrue(entered.wait(3))
                    second = threading.Thread(target=persist_second)
                    second.start()
                    proceed.set()
                    first.join(3)
                    second.join(3)
                    self.assertFalse(first.is_alive() or second.is_alive())
                self.assertEqual([], errors)
                self.assertEqual({11, 22}, {row['pid'] for row in json.loads(record.read_text())})
            finally:
                proceed.set()
                manager.close()

    @mock.patch("promptaflow.hub.process_identity", return_value="birth-token")
    def test_a_launched_runtime_is_recorded_as_owned_by_this_hub(
        self, _process_identity,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, workspace = registry.register(workspace)
            process = mock.Mock(pid=123)
            runtime = DiscoveredRuntime(root / "owner.lock", {
                "pid": 123, "project_root": str(workspace),
                "base_url": "http://127.0.0.1:41001",
            })
            observations = iter(((), (runtime,)))
            manager = WorkspaceRuntimeManager(
                registry=registry, runtime_discovery=lambda: next(observations),
                health_check=lambda _url: True, launcher=lambda _path: process,
                sleep=lambda _seconds: None,
            )

            self.assertEqual("http://127.0.0.1:41001", manager.ensure(identifier))
            owned = manager._owned_runtimes  # noqa: SLF001 - ownership contract
            self.assertEqual([123], list(owned))
            self.assertEqual("birth-token", owned[123].identity)
            self.assertEqual(str(workspace), owned[123].label)
            # The handle is what lets a finished child be reaped rather than
            # read as a zombie that never exits.
            self.assertIsNotNone(owned[123].handle)

    def test_a_launched_runtime_is_recorded_where_the_next_hub_finds_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "launched-runtimes.json"
            manager = WorkspaceRuntimeManager(
                registry=WorkspaceRegistry(path=Path(temporary) / "ws.json"),
                runtime_discovery=lambda: [],
                launcher=lambda _workspace: SimpleNamespace(pid=4242, poll=lambda: None),
                health_check=lambda _url: True,
                timeout_seconds=0,
                ownership_path=record,
            )
            self.addCleanup(manager.close)
            with patch("promptaflow.hub.process_identity", return_value="birth"):
                with contextlib.suppress(HubError):
                    manager.ensure(manager.registry.register(Path(temporary))[0])

            self.assertEqual(
                # Resolved: the registry canonicalises, and on macOS /var is a
                # symlink to /private/var.
                [{
                    "pid": 4242, "identity": "birth",
                    "workspace": str(Path(temporary).resolve()),
                }],
                json.loads(record.read_text(encoding="utf-8")),
            )
            manager.close()

    def test_a_new_hub_adopts_only_what_the_record_proves_is_its_own(self) -> None:
        """Discovery cannot say who started a Runtime; the birth token can.

        A Hub that was killed leaves its Runtimes alive with nothing to reap
        them. Adopting on a workspace match instead would take Runtimes a
        person started themselves — the collateral this scoping removed.
        """

        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "launched-runtimes.json"
            record.write_text(json.dumps([
                {
                    "pid": 11, "identity": "still-ours",
                    "workspace": "/work/a", "owner_token": "launch-a",
                },
                {"pid": 12, "identity": "pid-was-reused", "workspace": "/work/b"},
                {"pid": 13, "identity": "already-gone", "workspace": "/work/c"},
            ]), encoding="utf-8")

            identities = {11: "still-ours", 12: "somebody-else", 13: None}
            with patch(
                "promptaflow.hub.process_identity", side_effect=identities.get,
            ):
                manager = WorkspaceRuntimeManager(
                    runtime_discovery=lambda: [], ownership_path=record,
                )
                self.addCleanup(manager.close)

            owned = manager._owned_runtimes  # noqa: SLF001 - ownership contract
            self.assertEqual([11], list(owned))
            self.assertEqual("/work/a", owned[11].label)
            self.assertEqual("launch-a", owned[11].owner_token)
            # Not our child this time: there is nothing to reap, only to watch.
            self.assertIsNone(owned[11].handle)
            manager.close()

    def test_ownership_is_not_read_unless_a_path_was_supplied(self) -> None:
        """A manager built for a test or embedded elsewhere inherits nothing."""

        with patch("promptaflow.hub.process_identity", return_value="any") as probe:
            manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [])

        probe.assert_not_called()
        self.assertEqual({}, manager._owned_runtimes)  # noqa: SLF001

    def test_existing_runtime_for_the_workspace_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = WorkspaceRegistry(root / "workspaces.json")
            (root / "project").mkdir()
            identifier, workspace = registry.register(root / "project")
            runtime = DiscoveredRuntime(root / "owner.lock", {
                "project_root": str(workspace), "base_url": "http://127.0.0.1:41001",
            })
            launches = []
            manager = WorkspaceRuntimeManager(
                registry=registry, runtime_discovery=lambda: (runtime,),
                health_check=lambda _url: True,
                launcher=lambda path: launches.append(path),
            )

            self.assertEqual("http://127.0.0.1:41001", manager.ensure(identifier))
            self.assertEqual([], launches)

    def test_two_workspaces_start_and_resolve_independent_runtimes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = WorkspaceRegistry(root / "workspaces.json")
            (root / "first").mkdir()
            (root / "second").mkdir()
            first_id, first = registry.register(root / "first")
            second_id, second = registry.register(root / "second")
            active = {}

            def discover():
                return tuple(
                    DiscoveredRuntime(root / f"{identifier}.lock", {
                        "project_root": str(workspace), "base_url": url,
                    })
                    for identifier, (workspace, url) in active.items()
                )

            def launch(workspace):
                identifier = project_id(workspace)
                active[identifier] = (workspace, f"http://127.0.0.1:{41000 + len(active)}")

            manager = WorkspaceRuntimeManager(
                registry=registry, runtime_discovery=discover,
                health_check=lambda _url: True, launcher=launch, sleep=lambda _seconds: None,
            )

            first_url = manager.ensure(first_id)
            second_url = manager.ensure(second_id)
            self.assertNotEqual(first_url, second_url)
            self.assertEqual({first.resolve(), second.resolve()}, {item[0] for item in active.values()})

    def test_restart_overlap_waits_for_two_runtimes_to_converge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, workspace = registry.register(workspace)
            old = DiscoveredRuntime(root / "old.lock", {
                "project_root": str(workspace), "base_url": "http://127.0.0.1:41001",
            })
            new = DiscoveredRuntime(root / "new.lock", {
                "project_root": str(workspace), "base_url": "http://127.0.0.1:41002",
            })
            observations = iter(((old, new), (old, new), (new,)))
            launches = []
            manager = WorkspaceRuntimeManager(
                registry=registry,
                runtime_discovery=lambda: next(observations),
                health_check=lambda _url: True,
                launcher=lambda path: launches.append(path),
                sleep=lambda _seconds: None,
            )

            self.assertEqual("http://127.0.0.1:41002", manager.ensure(identifier))
            self.assertEqual([], launches)

    def test_startup_timeout_reports_runtime_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, _ = registry.register(workspace)
            now = [0.0]
            manager = WorkspaceRuntimeManager(
                registry=registry, runtime_discovery=lambda: (),
                health_check=lambda _url: False, launcher=lambda _path: None,
                timeout_seconds=0.25, clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            )

            with self.assertRaisesRegex(HubError, "did not become ready"):
                manager.ensure(identifier)

    def test_multiple_runtimes_are_reported_only_after_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "workspaces.json")
            identifier, workspace = registry.register(workspace)
            runtimes = tuple(
                DiscoveredRuntime(root / f"{index}.lock", {
                    "project_root": str(workspace),
                    "base_url": f"http://127.0.0.1:{41000 + index}",
                })
                for index in (1, 2)
            )
            now = [0.0]
            launches = []
            manager = WorkspaceRuntimeManager(
                registry=registry, runtime_discovery=lambda: runtimes,
                health_check=lambda _url: True,
                launcher=lambda path: launches.append(path),
                timeout_seconds=0.25, clock=lambda: now[0],
                sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
            )

            with self.assertRaisesRegex(
                MultipleRuntimesError, "remained live.*after 0.25s",
            ):
                manager.ensure(identifier)
            self.assertEqual([], launches)


class HubHttpTests(unittest.TestCase):
    class Manager:
        def __init__(self):
            self.identifiers = []

        def ensure(self, identifier=None):
            self.identifiers.append(identifier)
            return "http://127.0.0.1:41001"

    def test_initialize_is_owned_by_the_hub_without_starting_a_runtime(self) -> None:
        manager = self.Manager()
        with AsgiHarness(create_hub_app(manager)) as client:
            response = client.request("POST", "/mcp", body={
                "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
            })

        self.assertEqual("promptaflow", response.json()["result"]["serverInfo"]["name"])
        self.assertIn(
            "list_delegations", response.json()["result"]["instructions"],
        )
        self.assertTrue(response.headers["mcp-session-id"])
        self.assertEqual([], manager.identifiers)

    def test_workspace_registration_is_persisted_by_the_hub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            registry = WorkspaceRegistry(root / "hub" / "workspaces.json")
            grants = ProjectAccessGrants(root / "hub" / "project-access.json")
            manager = WorkspaceRuntimeManager(
                registry=registry, grants=grants, runtime_discovery=lambda: (),
            )
            with AsgiHarness(create_hub_app(manager)) as client:
                response = client.request(
                    "POST", "/internal/v1/workspaces/register",
                    body={"path": str(workspace), "create": False},
                )

            payload = response.json()
            identifier = project_id(workspace)
            self.assertEqual(200, response.status_code)
            self.assertEqual(identifier, payload["workspace_id"])
            self.assertEqual(str(workspace.resolve()), payload["workspace_path"])
            self.assertTrue(payload["mcp_url"].endswith(f"/workspaces/{identifier}/mcp"))
            self.assertEqual(workspace.resolve(), registry.resolve(identifier))
            self.assertTrue(grants.granted(identifier))

    def test_workspace_registration_cannot_create_an_arbitrary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = WorkspaceRuntimeManager(
                registry=WorkspaceRegistry(root / "hub" / "workspaces.json"),
                grants=ProjectAccessGrants(root / "hub" / "project-access.json"),
                runtime_discovery=lambda: (),
            )
            with AsgiHarness(create_hub_app(manager)) as client:
                response = client.request(
                    "POST", "/internal/v1/workspaces/register",
                    body={"path": str(root / "missing"), "create": True},
                )

            self.assertEqual(400, response.status_code)
            self.assertFalse((root / "missing").exists())

    def test_default_and_named_tool_requests_use_the_internal_backend(self) -> None:
        manager = self.Manager()
        app = create_hub_app(manager)
        answer = {"result": {"tools": [{"name": "list_runs"}]}}
        with mock.patch(
            "promptaflow.hub._forward",
            return_value=(200, json.dumps(answer).encode(), "application/json"),
        ) as forward, AsgiHarness(app) as client:
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            default = client.request("POST", "/mcp", body=request)
            named = client.request("POST", "/workspaces/project-a/mcp", body=request)

        for response in (default, named):
            names = [item["name"] for item in response.json()["result"]["tools"]]
            self.assertEqual("list_runs", names[0])
            self.assertIn("list_workspaces", names)
            self.assertIn("select_workspace", names)
        self.assertEqual([None, "project-a"], manager.identifiers)
        self.assertEqual(
            "http://127.0.0.1:41001/internal/v1/agent-tools",
            forward.call_args_list[0].args[0],
        )
        self.assertEqual(
            {"operation": "list"},
            json.loads(forward.call_args_list[0].args[1]),
        )
        self.assertEqual(
            {"content-type": "application/json"},
            forward.call_args_list[0].args[2],
        )

    def test_explicit_actor_is_forwarded_to_the_internal_backend(self) -> None:
        manager = self.Manager()
        answer = {"result": {"tools": []}}
        with mock.patch(
            "promptaflow.hub._forward",
            return_value=(200, json.dumps(answer).encode(), "application/json"),
        ) as forward, AsgiHarness(create_hub_app(manager)) as client:
            client.request(
                "POST", "/mcp", headers={"x-promptaflow-actor": "harness:session:abc"},
                body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )

        self.assertEqual(
            "harness:session:abc",
            forward.call_args.args[2]["x-promptaflow-actor"],
        )

    def test_blocking_forwards_have_a_dedicated_capacity_budget(self) -> None:
        app = create_hub_app(self.Manager(), forward_concurrency=24)

        self.assertEqual(24, app.state.forward_limiter.total_tokens)
        with self.assertRaisesRegex(ValueError, "must be positive"):
            create_hub_app(self.Manager(), forward_concurrency=0)

    def test_background_worker_claim_is_routed_across_online_workspaces(self) -> None:
        class Registry:
            def list(self):
                return [{
                    "workspace_id": "workspace-a", "path": "/projects/a",
                    "available": True,
                }]

            def resolve(self, identifier):
                self.assertEqual("workspace-a", identifier)

        class Manager:
            registry = Registry()

            def find_live(self, identifier):
                return "http://127.0.0.1:41001" if identifier == "workspace-a" else None

        payload = {"delegation": {"delegation_id": "app:one"}}
        with mock.patch(
            "promptaflow.hub._runtime_json", return_value=(200, payload),
        ) as forwarded, AsgiHarness(create_hub_app(Manager())) as client:
            response = client.request(
                "POST", "/internal/v1/background-delegations/claim",
                body={"worker_id": "machine-worker", "pools": ["default"]},
            )

        self.assertEqual("workspace-a", response.json()["workspace_id"])
        self.assertEqual("/projects/a", response.json()["workspace_path"])
        self.assertIn(
            "/internal/v1/background-delegations/claim",
            forwarded.call_args.args[0],
        )

    def test_list_workspaces_reports_unavailable_registrations(self) -> None:
        manager = self.Manager()

        class Registry:
            calls = 0

            def list(self):
                self.calls += 1
                return [{
                    "workspace_id": "missing", "name": "Missing",
                    "path": "/projects/missing", "kind": "registered",
                    "available": False,
                }]

        manager.registry = Registry()
        with AsgiHarness(create_hub_app(manager)) as client:
            response = client.request("POST", "/mcp", body={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "list_workspaces", "arguments": {}},
            })

        payload = response.json()["result"]
        self.assertFalse(payload["structuredContent"]["workspaces"][0]["available"])
        self.assertEqual(1, manager.registry.calls)

    def test_a_session_can_select_a_workspace_by_readable_name(self) -> None:
        manager = self.Manager()

        class Registry:
            def list(self):
                return [{
                    "workspace_id": "project-a", "name": "PromptaFlow Project",
                    "path": "/projects/promptaflow", "kind": "registered",
                }]

            def select(self, **selection):
                self.selection = selection
                return "project-a"

        manager.registry = Registry()
        backend = {"result": {"tools": []}}
        with mock.patch(
            "promptaflow.hub._forward",
            return_value=(200, json.dumps(backend).encode(), "application/json"),
        ), AsgiHarness(create_hub_app(manager)) as client:
            initialized = client.request("POST", "/mcp", body={
                "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
            })
            session_id = initialized.headers["mcp-session-id"]
            headers = {"mcp-session-id": session_id}
            selected = client.request("POST", "/mcp", headers=headers, body={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {
                    "name": "select_workspace",
                    "arguments": {"name": "PromptaFlow Project"},
                },
            })
            client.request("POST", "/mcp", headers=headers, body={
                "jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {},
            })

        self.assertFalse(selected.json()["result"]["isError"])
        self.assertEqual({"path": None, "name": "PromptaFlow Project"}, manager.registry.selection)
        self.assertEqual(["project-a"], manager.identifiers)

    def test_ui_redirects_to_the_selected_runtime(self) -> None:
        manager = self.Manager()
        with AsgiHarness(create_hub_app(manager)) as client:
            response = client.get("/workspaces/project-a/ui/assets/app.js?theme=dark")

        self.assertEqual(307, response.status_code)
        self.assertEqual(
            "http://127.0.0.1:41001/ui/assets/app.js?theme=dark",
            response.headers["location"],
        )
        self.assertEqual(["project-a"], manager.identifiers)


class HubGlobalControlTests(unittest.TestCase):
    class Registry:
        def list(self):
            return [{
                "workspace_id": "project-a", "name": "Project A",
                "path": "/projects/a", "kind": "registered", "available": True,
            }, {
                "workspace_id": "project-b", "name": "Project B",
                "path": "/projects/b", "kind": "registered", "available": True,
            }]

    class Manager:
        def __init__(self):
            self.registry = HubGlobalControlTests.Registry()

        def ensure(self, identifier):
            self.ensured = identifier
            return "http://127.0.0.1:41001"

        def find_live(self, identifier):
            return "http://127.0.0.1:41001" if identifier == "project-a" else None

    def test_template_is_global_then_published_by_target_runtime(self) -> None:
        source = json.dumps({
            "dsl_version": "1.0",
            "metadata": {"id": "shared", "name": "Shared"},
            "nodes": [], "edges": [],
        })
        manager = self.Manager()
        with tempfile.TemporaryDirectory() as temporary:
            store = WorkflowTemplateStore(Path(temporary) / "templates.json")
            with mock.patch(
                "promptaflow.hub._runtime_json",
                return_value=(201, {"data": {"workflow_id": "workflow:shared", "version": 1}}),
            ) as runtime, AsgiHarness(create_hub_app(manager, template_store=store)) as client:
                created = client.request("POST", "/api/v1/workflow-templates", body={
                    "name": "Shared", "source": source, "expected_version": 0,
                }, headers={"idempotency-key": "template-1"})
                template_id = created.json()["template_id"]
                listed = client.get("/api/v1/workflow-templates")
                imported = client.request(
                    "POST", f"/api/v1/workflow-templates/{template_id}/instantiate",
                    headers={"idempotency-key": "import-1"},
                    body={"workspace_id": "project-a", "expected_latest_version": 0},
                )

        self.assertEqual(201, created.status_code)
        self.assertEqual(1, len(listed.json()["templates"]))
        self.assertEqual(201, imported.status_code)
        self.assertEqual("project-a", manager.ensured)
        call = runtime.call_args.args[0]
        self.assertIn("/api/v1/workflows/workflow:shared/versions", call)
        self.assertEqual("import-1", runtime.call_args.kwargs["headers"]["idempotency-key"])

    def test_agent_statistics_sum_only_live_workspace_runtimes(self) -> None:
        catalog = {"data": {"handlers": [{
            "name": "agent.codex", "version": "1.2.3",
            "attempt_count": 7, "failed_count": 2,
        }, {"name": "transform", "attempt_count": 99, "failed_count": 99}]}}
        with mock.patch(
            "promptaflow.hub._runtime_json", return_value=(200, catalog),
        ), AsgiHarness(create_hub_app(self.Manager())) as client:
            response = client.get("/api/v1/global/agent-stats")

        payload = response.json()
        self.assertEqual([{
            "name": "agent.codex", "attempt_count": 7, "failed_count": 2,
            "workspaces": 1, "versions": ["1.2.3"],
        }], payload["agents"])
        self.assertEqual(
            ["online", "offline"],
            [item["runtime"] for item in payload["workspaces"]],
        )
        self.assertEqual("sum_of_workspace_runtime_statistics", payload["semantics"])

    def test_a_malformed_catalog_costs_one_workspace_not_the_endpoint(self) -> None:
        """The per-Workspace guard has to actually cover what a Runtime can say.

        `{"data": null}` and a null tally raise AttributeError and TypeError,
        neither of which the guard caught, so one older or half-booted Runtime
        took the machine-wide statistics down with a 500. And the Workspace was
        appended "online" before the totals were summed, so a failure mid-way
        listed it twice, contradicting itself, over half-added numbers.
        """

        with mock.patch(
            "promptaflow.hub._runtime_json", return_value=(200, {"data": None}),
        ), AsgiHarness(create_hub_app(self.Manager())) as client:
            response = client.get("/api/v1/global/agent-stats")

        self.assertEqual(200, response.status_code, response.text)
        payload = response.json()
        self.assertEqual([], payload["agents"])
        states = [item["runtime"] for item in payload["workspaces"]]
        self.assertEqual(len(states), len(payload["workspaces"]))
        self.assertNotIn("error", states, "a null `data` is an empty catalog")

    def test_a_workspace_that_fails_mid_sum_contributes_nothing(self) -> None:
        """All of a Workspace's numbers, or none: never half of them."""

        catalog = {"data": {"handlers": [
            {"name": "agent.codex", "attempt_count": 7, "failed_count": 0},
            {"name": "agent.claude", "attempt_count": [], "failed_count": 0},
        ]}}
        with mock.patch(
            "promptaflow.hub._runtime_json", return_value=(200, catalog),
        ), AsgiHarness(create_hub_app(self.Manager())) as client:
            response = client.get("/api/v1/global/agent-stats")

        payload = response.json()
        self.assertEqual(200, response.status_code, response.text)
        # An unreadable tally is zero, not a refusal and not a partial sum.
        self.assertEqual(
            {"agent.claude": 0, "agent.codex": 7},
            {item["name"]: item["attempt_count"] for item in payload["agents"]},
        )
        self.assertEqual(
            1, sum(1 for item in payload["workspaces"] if item["runtime"] == "online"),
        )

    def test_global_template_writes_require_concurrency_controls(self) -> None:
        source = json.dumps({
            "dsl_version": "1.0",
            "metadata": {"id": "shared", "name": "Shared"},
            "nodes": [], "edges": [],
        })
        with tempfile.TemporaryDirectory() as temporary, AsgiHarness(create_hub_app(
            self.Manager(), template_store=WorkflowTemplateStore(
                Path(temporary) / "templates.json"
            ),
        )) as client:
            missing_key = client.request(
                "POST", "/api/v1/workflow-templates",
                body={"name": "Shared", "source": source, "expected_version": 0},
            )
            missing_version = client.request(
                "POST", "/api/v1/workflow-templates",
                headers={"idempotency-key": "template-1"},
                body={"name": "Shared", "source": source},
            )

        self.assertEqual(400, missing_key.status_code)
        self.assertIn("idempotency-key", missing_key.text)
        self.assertEqual(400, missing_version.status_code)
        self.assertIn("expected_version", missing_version.text)

    def test_corrupt_global_template_catalog_is_unavailable_not_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "templates.json"
            path.write_text("{broken", encoding="utf-8")
            with AsgiHarness(create_hub_app(
                self.Manager(), template_store=WorkflowTemplateStore(path),
            )) as client:
                read = client.get("/api/v1/workflow-templates")
                write = client.request(
                    "POST", "/api/v1/workflow-templates",
                    headers={"idempotency-key": "new"},
                    body={
                        "name": "x", "expected_version": 0,
                        "source": json.dumps({
                            "dsl_version": "1.0",
                            "metadata": {"id": "x", "name": "x"},
                            "nodes": [], "edges": [],
                        }),
                    },
                )

            self.assertEqual(503, read.status_code)
            self.assertEqual(503, write.status_code)
            self.assertEqual("{broken", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
