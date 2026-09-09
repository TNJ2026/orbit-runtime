"""Native Windows launchers mirror the three Bash entry points."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class PowerShellScriptTests(unittest.TestCase):
    def run_script(self, script: Path, *arguments: str, cwd: Path, env=None):
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                *arguments,
            ],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def fake_orbit(root: Path) -> tuple[Path, Path]:
        capture = root / "arguments.jsonl"
        script = root / "fake-orbit.ps1"
        script.write_text(
            "param([Parameter(ValueFromRemainingArguments=$true)]"
            "[string[]]$Items)\n"
            "if ($Items.Count -ge 2 -and $Items[0] -eq 'runtimes') {\n"
            "  if ($env:ORBIT_TEST_RUNTIME_JSON) {\n"
            "    Write-Output $env:ORBIT_TEST_RUNTIME_JSON\n"
            "  } else {\n"
            "    Write-Output '[]'\n"
            "  }\n"
            "  exit 0\n"
            "}\n"
            "$Items | ConvertTo-Json -Compress | "
            "Add-Content -LiteralPath $env:ORBIT_TEST_CAPTURE -Encoding UTF8\n"
            "if ($Items.Count -ge 2 -and $Items[0] -eq 'hub' "
            "-and $Items[1] -eq 'register') {\n"
            "  Write-Output '{\"ui_url\":\"http://127.0.0.1:8848/"
            "workspaces/example/ui/\"}'\n"
            "}\n",
            encoding="utf-8",
        )
        return script, capture

    def test_start_ensures_the_windows_app_and_registers_the_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            fake, capture = self.fake_orbit(Path(temporary))
            environment = {
                **os.environ,
                "PROMPTAFLOW_CLI": str(fake),
                "ORBIT_TEST_CAPTURE": str(capture),
                "ORBIT_TEST_RUNTIME_JSON": json.dumps([{
                    "project_root": str(workspace.resolve()),
                    "base_url": "http://127.0.0.1:51234",
                }]),
            }

            result = self.run_script(
                ROOT / "start-promptaflow.ps1", str(workspace / "."),
                cwd=ROOT, env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            calls = [
                json.loads(line)
                for line in capture.read_text(encoding="utf-8-sig").splitlines()
            ]
            self.assertEqual(
                ["agent-app", "ensure", str(ROOT / "agent-app.windows.json")],
                calls[0],
            )
            self.assertEqual(
                ["hub", "register", str(workspace.resolve())], calls[1],
            )
            self.assertIn("PromptaFlow Hub: http://127.0.0.1:8848", result.stdout)
            self.assertIn(
                "Workspace UI: "
                "http://127.0.0.1:8848/workspaces/example/ui/",
                result.stdout,
            )
            self.assertIn(
                "Workspace Runtime: http://127.0.0.1:51234", result.stdout,
            )

    def test_start_rejects_a_missing_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake, capture = self.fake_orbit(Path(temporary))
            environment = {
                **os.environ,
                "PROMPTAFLOW_CLI": str(fake),
                "ORBIT_TEST_CAPTURE": str(capture),
            }

            result = self.run_script(
                ROOT / "start-promptaflow.ps1", str(Path(temporary) / "missing"),
                cwd=ROOT, env=environment,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("is not a directory", result.stderr)
            self.assertFalse(capture.exists())

    def test_internal_hub_mode_uses_the_same_orbit_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake, capture = self.fake_orbit(Path(temporary))
            environment = {
                **os.environ,
                "PROMPTAFLOW_CLI": str(fake),
                "ORBIT_TEST_CAPTURE": str(capture),
            }

            result = self.run_script(
                ROOT / "start-promptaflow.ps1", "-HubService",
                cwd=ROOT, env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                ["hub", "serve"],
                json.loads(capture.read_text(encoding="utf-8-sig").strip()),
            )

    @unittest.skipUnless(os.name == "nt", "requires Windows process APIs")
    def test_restart_dry_run_with_empty_state_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            fake, capture = self.fake_orbit(isolated)
            (isolated / "restart-promptaflow.ps1").write_text(
                (ROOT / "restart-promptaflow.ps1").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            manifest = json.loads(
                (ROOT / "agent-app.windows.json").read_text(encoding="utf-8")
            )
            manifest["service"]["ready_url"] = (
                "http://127.0.0.1:59773/health/ready"
            )
            (isolated / "agent-app.windows.json").write_text(
                json.dumps(manifest), encoding="utf-8",
            )
            state = isolated / "agent-app-state"
            runtime = isolated / "runtime-state"
            state.mkdir()
            runtime.mkdir()
            environment = {
                **os.environ,
                "PROMPTAFLOW_CLI": str(fake),
                "ORBIT_TEST_CAPTURE": str(capture),
                "AGENT_APP_STATE_DIR": str(state),
                "ORBIT_RUNTIME_ROOT": str(runtime),
            }

            result = self.run_script(
                isolated / "restart-promptaflow.ps1", "-DryRun",
                cwd=isolated, env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Nothing of PromptaFlow's is running.", result.stdout)
            self.assertIn("nothing was stopped or started", result.stdout)

    def test_windows_manifest_launches_the_powershell_hub_mode(self):
        from promptaflow.agent_apps.manifest import load_manifest

        loaded = load_manifest(ROOT / "agent-app.windows.json")
        manifest = json.loads(
            (ROOT / "agent-app.windows.json").read_text(encoding="utf-8")
        )
        command = manifest["service"]["command"]

        self.assertEqual("promptaflow", loaded.app_id)
        self.assertEqual("powershell.exe", command[0])
        self.assertIn("{manifest_dir}/start-promptaflow.ps1", command)
        self.assertEqual("-HubService", command[-1])
        self.assertIn("USERPROFILE", manifest["service"]["environment"])
        self.assertIn("USERNAME", manifest["service"]["environment"])
        self.assertIn("PATHEXT", manifest["service"]["environment"])
        self.assertIn("COMSPEC", manifest["service"]["environment"])
        self.assertIn("APPDATA", manifest["service"]["environment"])
        self.assertIn("LOCALAPPDATA", manifest["service"]["environment"])

    def test_codex_mcp_config_uses_the_cross_platform_launcher(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["promptaflow"]

        self.assertEqual("uv", server["command"])
        self.assertEqual(
            [
                "run", "--project", ".", "promptaflow",
                "agent-app", "mcp-proxy",
            ],
            server["args"],
        )
        self.assertEqual(".", server["cwd"])
        self.assertEqual(
            {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            server["env"],
        )
        for variable in (
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "PATH",
            "PATHEXT",
            "COMSPEC",
            "USERNAME",
            "PROMPTAFLOW_AGENT_APP_WORKSPACE",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
        ):
            self.assertIn(variable, server["env_vars"])

    def test_mcp_proxy_forces_utf8_for_the_orbit_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "encoding.json"
            fake = root / "fake-orbit.ps1"
            fake.write_text(
                "@{ PYTHONUTF8 = $env:PYTHONUTF8; "
                "PYTHONIOENCODING = $env:PYTHONIOENCODING } | "
                "ConvertTo-Json -Compress | "
                "Set-Content -LiteralPath $env:ORBIT_TEST_CAPTURE -Encoding UTF8\n",
                encoding="utf-8",
            )
            environment = {
                **os.environ,
                "PROMPTAFLOW_CLI": str(fake),
                "ORBIT_TEST_CAPTURE": str(capture),
                "PYTHONUTF8": "0",
                "PYTHONIOENCODING": "cp936",
            }

            result = self.run_script(
                ROOT / "start-promptaflow.ps1", "-McpProxy",
                cwd=ROOT, env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            encoding = json.loads(capture.read_text(encoding="utf-8-sig"))
            self.assertEqual("1", encoding["PYTHONUTF8"])
            self.assertEqual("utf-8", encoding["PYTHONIOENCODING"])

    def test_stop_delegates_to_the_identity_checked_restart_path(self):
        contents = (ROOT / "stop-promptaflow.ps1").read_text(encoding="utf-8")

        self.assertIn('"restart-promptaflow.ps1"', contents)
        self.assertIn("StopOnly = $true", contents)

    def test_cmd_launchers_bypass_policy_for_only_the_child_process(self):
        for action in ("start", "restart", "stop"):
            with self.subTest(action=action):
                contents = (ROOT / f"{action}-orbit.cmd").read_text(encoding="utf-8")
                self.assertIn("powershell.exe -NoProfile -ExecutionPolicy Bypass", contents)
                self.assertIn(f'"%~dp0{action}-orbit.ps1" %*', contents)
                self.assertIn("exit /b %ERRORLEVEL%", contents)


if __name__ == "__main__":
    unittest.main()
