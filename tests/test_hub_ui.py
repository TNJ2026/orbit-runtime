import asyncio
import re
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from promptaflow.hub import WorkspaceRuntimeManager, create_hub_app
from promptaflow.platform.runtime_ownership import DiscoveredRuntime
from promptaflow.web.hub_ui import render_hub_ui
from tests.test_web_composition import AsgiHarness


class HubUiTests(unittest.TestCase):
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
            manager.stop_all.return_value = {
                "requested": ["/work/a"], "terminated": ["/work/b"], "failures": [],
            }
            response = client.request(
                "POST", "/api/v1/hub/shutdown",
                headers={"x-promptaflow-shutdown-token": token},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual("stopping", response.json()["status"])
            self.assertEqual([], stopped)
            client._loop.run_until_complete(asyncio.sleep(0.06))
            self.assertEqual([True], stopped)
        # The successful endpoint call stops them before answering; lifespan
        # repeats the idempotent cleanup for every normal Hub exit path.
        self.assertEqual(3, manager.stop_all.call_count)

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
            10: ("graceful-birth", "/work/a"),
            11: ("starting-birth", "/work/b"),
        }
        result = manager.stop_all()

        self.assertEqual(["/work/a"], result["requested"])
        self.assertEqual(["/work/b"], result["terminated"])
        self.assertEqual([], result["failures"])
        stop_pid_tree.assert_called_once_with(11, "starting-birth")

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
            10: ("stuck-birth", "/work/a"),
        }
        result = manager.stop_all()

        self.assertEqual(["/work/a"], result["requested"])
        self.assertEqual(["/work/a"], result["terminated"])
        self.assertEqual([], result["failures"])
        stop_pid_tree.assert_called_once_with(10, "stuck-birth")

    def test_stop_all_reports_an_owned_pid_without_a_birth_identity_as_failure(self):
        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [])
        manager._owned_runtimes = {10: (None, "/work/a")}  # noqa: SLF001

        result = manager.stop_all()

        self.assertEqual([], result["requested"])
        self.assertEqual([], result["terminated"])
        self.assertEqual(["/work/a"], result["failures"])

    def test_stop_all_does_not_touch_a_runtime_owned_by_another_hub(self):
        foreign = DiscoveredRuntime(Path('/foreign.lock'), {
            'pid': 99, 'project_root': '/work/foreign',
            'base_url': 'http://127.0.0.1:41999',
        })
        manager = WorkspaceRuntimeManager(runtime_discovery=lambda: [foreign])

        result = manager.stop_all()

        self.assertEqual({"requested": [], "terminated": [], "failures": []}, result)
