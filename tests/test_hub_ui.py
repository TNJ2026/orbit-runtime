import asyncio
import re
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from promptaflow.hub import WorkspaceRuntimeManager, create_hub_app
from promptaflow.hub import _OwnedRuntime  # noqa: PLC2701 - ownership record under test
from promptaflow.platform.runtime_ownership import DiscoveredRuntime
from promptaflow.web.hub_ui import render_hub_ui
from tests.test_web_composition import AsgiHarness


class HubUiTests(unittest.TestCase):
    @patch("promptaflow.hub.process_identity", return_value="birth-token")
    def test_owned_process_handle_is_authoritative_when_it_has_exited(
        self, process_identity,
    ):
        """Windows keeps birth metadata readable while Popen owns the handle."""

        from promptaflow.hub import _wait_for_process_exit

        handle = Mock()
        handle.poll.return_value = 0

        self.assertTrue(_wait_for_process_exit(10, "birth-token", 0, handle))
        process_identity.assert_not_called()

    def runtime(self, path, url):
        return DiscoveredRuntime(Path('/unused'), {'project_root': path, 'base_url': url})

    def test_lists_healthy_runtimes_without_launching_or_registering(self):
        registry = Mock()
        launcher = Mock()
        manager = WorkspaceRuntimeManager(
            registry=registry, launcher=launcher,
            runtime_discovery=lambda: [
                self.runtime('/work/a', 'http://127.0.0.1:41001'),
                self.runtime('/work/<b>&', 'http://127.0.0.1:41002'),
                self.runtime('/work/offline', 'http://127.0.0.1:41003'),
                self.runtime('/work/unsafe', 'javascript:alert(1)'),
            ], health_check=lambda url: not url.endswith('41003'),
        )
        with AsgiHarness(create_hub_app(manager)) as client:
            for path in ('/ui', '/ui/'):
                response = client.get(path)
                self.assertEqual(200, response.status_code)
                body = response.content.decode()
                self.assertIn('2 个运行中的 Runtime', body)
                self.assertIn('/work/a', body)
                self.assertIn('/work/&lt;b&gt;&amp;', body)
                self.assertIn('href="http://127.0.0.1:41002/ui/"', body)
                self.assertIn('<code>41001</code>', body)
                self.assertNotIn('/work/offline', body)
                self.assertNotIn('javascript:', body)
                self.assertEqual('no-store', response.headers['cache-control'])
        launcher.assert_not_called()
        self.assertEqual([], registry.mock_calls)

    def test_every_surface_takes_its_colour_from_the_palette(self):
        """A page with two colour schemes has to be painted in both.

        The table was given a literal dark panel while `--text` in the light
        scheme is near-black, so the two columns carrying the answer — which
        workspace, which port — were black on black for anybody not in dark
        mode. Everything else on the page already read from the palette, which
        is defined for both schemes; that one surface did not.

        Checked as the rule rather than as the colour: a literal is allowed
        only where the same selector is given a value in the dark block too,
        which is how `.status` says green twice.
        """

        css = render_hub_ui([]).split("<style>")[1].split("</style>")[0]
        dark = "".join(re.findall(r"@media\(prefers-color-scheme:dark\)\{(.*)\}", css))
        # What is left once both palettes are removed: the rules that paint.
        painting = re.sub(r":root[^{]*\{[^}]*\}", "", css)
        painting = re.sub(r"@media[^{]*\{.*?\}\s*\}", "", painting, flags=re.S)

        literals = [
            declaration
            for declaration in re.findall(
                r"(?:background|border[a-z-]*|color)\s*:[^;}]*", painting,
            )
            if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", declaration)
        ]
        # `.status` is the one that may: its dark value is right there.
        self.assertEqual(["color:#258353"], literals, painting)
        self.assertIn(".status{color:", dark)

    def test_header_uses_the_promptaflow_workflow_mark(self):
        body = render_hub_ui([])
        self.assertIn('<svg class="mark" viewBox="0 0 20 20"', body)
        self.assertIn('<path class="flow" d="M5.5 15.5v-11h4.6', body)
        self.assertIn('<circle class="terminal" cx="16" cy="15.5" r="1.7"/>', body)
        self.assertIn('<h1>PromptaFlow Hub</h1>', body)

    def test_empty_list_does_not_start_default_runtime(self):
        launcher = Mock()
        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [], launcher=launcher)
        with AsgiHarness(create_hub_app(manager)) as client:
            response = client.get('/ui')
        self.assertEqual(200, response.status_code)
        self.assertIn('暂无运行中的 Runtime', response.content.decode())
        launcher.assert_not_called()

    def test_shutdown_button_stops_all_runtimes_then_the_hub(self):
        stopped = []
        manager = Mock(spec=WorkspaceRuntimeManager)
        manager.live_ui_entries.return_value = []
        manager.stop_all.return_value = {
            "requested": ["/work/a"], "terminated": ["/work/b"], "failures": [],
        }
        with AsgiHarness(create_hub_app(
            manager, shutdown_request=lambda: stopped.append(True),
        )) as client:
            body = client.get('/ui').content.decode()
            self.assertIn('关闭 PromptaFlow', body)
            token = re.search(
                r"x-promptaflow-shutdown-token': '([^']+)'", body,
            ).group(1)
            denied = client.request(
                "POST", "/api/v1/hub/shutdown",
                headers={"x-promptaflow-shutdown-token": "wrong"},
            )
            self.assertEqual(403, denied.status_code)
            manager.stop_all.return_value = {
                "requested": [], "terminated": [], "failures": ["/work/stuck"],
            }
            failed = client.request(
                "POST", "/api/v1/hub/shutdown",
                headers={"x-promptaflow-shutdown-token": token},
            )
            self.assertEqual(503, failed.status_code)
            self.assertEqual([], stopped)
            self.assertFalse(hasattr(client.app.state, "runtime_shutdown"))
            manager.stop_all.return_value = {
                "requested": ["/work/a"], "terminated": ["/work/b"], "failures": [],
            }
            response = client.request(
                "POST", "/api/v1/hub/shutdown",
                headers={"x-promptaflow-shutdown-token": token},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual("stopping", response.json()["status"])
            self.assertEqual(
                manager.stop_all.return_value,
                client.app.state.runtime_shutdown,
            )
            self.assertEqual([], stopped)
            client._loop.run_until_complete(asyncio.sleep(0.06))
            self.assertEqual([True], stopped)
        # The failed request and the successful request each try once. After
        # success lifespan sees the recorded outcome and does not sweep again.
        self.assertEqual(2, manager.stop_all.call_count)

    def test_lifespan_shutdown_stops_runtimes_without_the_http_endpoint(self):
        manager = Mock(spec=WorkspaceRuntimeManager)
        manager.stop_all.return_value = {
            "requested": ["/work/a"], "terminated": [], "failures": [],
        }

        app = create_hub_app(manager, shutdown_request=lambda: None)
        with AsgiHarness(app):
            manager.stop_all.assert_not_called()

        manager.stop_all.assert_called_once_with()
        self.assertEqual(
            {"requested": ["/work/a"], "terminated": [], "failures": []},
            app.state.runtime_shutdown,
        )

    def test_route_cleanup_failure_is_answered_as_json_not_a_500(self):
        """The operator has to be able to read why, and the Hub must stay up.

        `discover_runtimes` reaches the filesystem through `is_dir()` and
        `rglob()` and catches no `OSError`, so this is the same fault the
        lifespan guard was added for. Unguarded here it becomes a non-JSON 500:
        the Hub page cannot parse it, and the operator is told the shutdown
        failed with nothing saying what happened.
        """

        stopped: list[bool] = []
        manager = Mock(spec=WorkspaceRuntimeManager)
        manager.live_ui_entries.return_value = []
        manager.stop_all.side_effect = OSError("discovery unavailable")
        with AsgiHarness(create_hub_app(
            manager, shutdown_request=lambda: stopped.append(True),
        )) as client:
            body = client.get("/ui").content.decode()
            token = re.search(
                r"x-promptaflow-shutdown-token': '([^']+)'", body,
            ).group(1)
            response = client.request(
                "POST", "/api/v1/hub/shutdown",
                headers={"x-promptaflow-shutdown-token": token},
            )

        self.assertEqual(503, response.status_code)
        self.assertEqual(
            "OSError: discovery unavailable", response.json()["details"],
        )
        self.assertEqual([], stopped, "the Hub must not close on a failed sweep")

    def test_lifespan_cleanup_failure_is_reported_without_failing_shutdown(self):
        manager = Mock(spec=WorkspaceRuntimeManager)
        manager.stop_all.side_effect = OSError("discovery unavailable")
        app = create_hub_app(manager, shutdown_request=lambda: None)

        with AsgiHarness(app):
            pass

        self.assertEqual(
            "OSError: discovery unavailable", app.state.runtime_shutdown_error,
        )

    def test_embedded_app_lifespan_does_not_stop_machine_runtimes(self):
        manager = Mock(spec=WorkspaceRuntimeManager)

        with AsgiHarness(create_hub_app(manager)):
            pass

        manager.stop_all.assert_not_called()

    @patch("promptaflow.hub._wait_for_process_exit")
    @patch("promptaflow.hub.stop_pid_tree_if_identity")
    @patch("promptaflow.hub._runtime_json")
    def test_stop_all_uses_the_runtime_api_then_falls_back_to_the_owned_pid(
        self, runtime_json, stop_pid_tree, wait_for_exit,
    ):
        graceful = DiscoveredRuntime(Path('/a.lock'), {
            'pid': 10, 'project_root': '/work/a',
            'base_url': 'http://127.0.0.1:41001',
        })
        starting = DiscoveredRuntime(Path('/b.lock'), {
            'pid': 11, 'project_root': '/work/b',
        })
        runtime_json.return_value = (200, {"data": {"status": "stopping"}})
        # The HTTP-requested Runtime exits inside its grace period. The Runtime
        # without an endpoint needs the process-tree fallback, which is then
        # verified independently of its discovery record.
        wait_for_exit.side_effect = [True, True]
        stop_pid_tree.return_value = True

        manager = WorkspaceRuntimeManager(
            runtime_discovery=lambda: [graceful, starting],
        )
        manager._owned_runtimes = {  # noqa: SLF001 - manager ownership fixture
            10: _OwnedRuntime("graceful-birth", "/work/a"),
            11: _OwnedRuntime("starting-birth", "/work/b"),
        }
        result = manager.stop_all()

        self.assertEqual(["/work/a"], result["requested"])
        self.assertEqual(["/work/b"], result["terminated"])
        self.assertEqual([], result["failures"])
        stop_pid_tree.assert_called_once_with(11, "starting-birth")

    @patch("promptaflow.hub._wait_for_process_exit", return_value=True)
    @patch("promptaflow.hub.stop_pid_tree_if_identity")
    @patch("promptaflow.hub._runtime_json", return_value=(200, {}))
    def test_stop_all_matches_a_windows_launcher_to_its_runtime_by_workspace(
        self, runtime_json, stop_pid_tree, _wait_for_exit,
    ):
        """A Windows console shim and its Python child publish different PIDs."""

        runtime = DiscoveredRuntime(Path('/runtime.lock'), {
            'pid': 101, 'project_root': '/work/a',
            'base_url': 'http://127.0.0.1:41001',
        })
        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [runtime])
        manager._owned_runtimes = {  # noqa: SLF001 - manager ownership fixture
            100: _OwnedRuntime("launcher-birth", "/work/a"),
        }

        result = manager.stop_all()

        self.assertEqual(["/work/a"], result["requested"])
        self.assertEqual([], result["terminated"])
        self.assertEqual([], result["failures"])
        runtime_json.assert_called_once()
        stop_pid_tree.assert_not_called()

    @patch("promptaflow.hub._wait_for_process_exit")
    @patch("promptaflow.hub.stop_pid_tree_if_identity")
    @patch("promptaflow.hub._runtime_json", return_value=(200, {}))
    def test_stop_all_kills_a_runtime_that_unregistered_but_did_not_exit(
        self, _runtime_json, stop_pid_tree, wait_for_exit,
    ):
        runtime = DiscoveredRuntime(Path('/a.lock'), {
            'pid': 10, 'project_root': '/work/a',
            'base_url': 'http://127.0.0.1:41001',
        })
        wait_for_exit.side_effect = [False, True]
        stop_pid_tree.return_value = True

        manager = WorkspaceRuntimeManager(
            runtime_discovery=lambda: [runtime],
        )
        manager._owned_runtimes = {  # noqa: SLF001 - manager ownership fixture
            10: _OwnedRuntime("stuck-birth", "/work/a"),
        }
        result = manager.stop_all()

        self.assertEqual(["/work/a"], result["requested"])
        self.assertEqual(["/work/a"], result["terminated"])
        self.assertEqual([], result["failures"])
        stop_pid_tree.assert_called_once_with(10, "stuck-birth")

    def test_stop_all_forgets_an_owned_pid_it_can_never_identify(self):
        """A phantom must not make the Hub unstoppable for the rest of its life.

        `ensure` records the birth token straight after `Popen`, and it is
        `None` when the Runtime dies in its first milliseconds or `ps` times
        out. Reporting that as a failure and keeping the record meant every
        later sweep failed the same way, and `shutdown_hub` refuses while any
        failure stands — so the Hub could never be stopped again, over a
        process that had never started.
        """

        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [])
        manager._owned_runtimes = {10: _OwnedRuntime(None, "/work/a")}  # noqa: SLF001

        with patch("promptaflow.hub.process_identity", return_value=None):
            result = manager.stop_all()

        self.assertEqual([], result["requested"])
        self.assertEqual([], result["terminated"])
        self.assertEqual([], result["failures"])
        self.assertEqual({}, manager._owned_runtimes)  # noqa: SLF001

    def test_stop_all_re_probes_an_identity_recorded_too_early(self):
        """The record may predate the process being identifiable."""

        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [])
        manager._owned_runtimes = {10: _OwnedRuntime(None, "/work/a")}  # noqa: SLF001

        # Identifiable on the re-probe, gone once it has been signalled.
        with (
            patch(
                "promptaflow.hub.process_identity",
                side_effect=["late-birth", None],
            ),
            patch("promptaflow.hub.stop_pid_tree_if_identity", return_value=True) as stop,
        ):
            result = manager.stop_all()

        stop.assert_called_once_with(10, "late-birth")
        self.assertEqual(["/work/a"], result["terminated"])
        self.assertEqual({}, manager._owned_runtimes)  # noqa: SLF001

    def test_stop_all_does_not_touch_a_runtime_owned_by_another_hub(self):
        foreign = DiscoveredRuntime(Path('/foreign.lock'), {
            'pid': 99, 'project_root': '/work/foreign',
            'base_url': 'http://127.0.0.1:41999',
        })
        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [foreign])

        result = manager.stop_all()

        self.assertEqual({"requested": [], "terminated": [], "failures": []}, result)
