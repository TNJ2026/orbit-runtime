"""The repository/personal Marketplace release is self-contained."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "build-marketplace-release.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("orbit_marketplace_builder", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketplaceReleaseTests(unittest.TestCase):
    def test_archive_contains_the_mcp_launcher_and_plugin_metadata(self) -> None:
        builder = load_builder()
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "orbit-marketplace.zip"
            builder.build(archive, None)
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())

        root = "orbit-marketplace/plugins/orbit/"
        self.assertIn("orbit-marketplace/.agents/plugins/marketplace.json", names)
        self.assertIn(root + ".codex-plugin/plugin.json", names)
        self.assertIn(root + ".mcp.json", names)
        self.assertIn(root + "agent-app.windows.json", names)
        self.assertIn(root + "restart-orbit.cmd", names)
        self.assertIn(root + "restart-orbit.ps1", names)
        self.assertIn(root + "start-orbit.cmd", names)
        self.assertIn(root + "start-orbit.ps1", names)
        self.assertIn(root + "start-orbit.sh", names)
        self.assertIn(root + "stop-orbit.cmd", names)
        self.assertIn(root + "stop-orbit.ps1", names)
        self.assertIn(root + "skills/orbit/SKILL.md", names)

    def test_standalone_plugin_archive_contains_a_plugin_root(self) -> None:
        builder = load_builder()
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "orbit-plugin.zip"
            builder.build_plugin(archive, None)
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())

        root = "orbit-plugin/"
        self.assertIn(root + ".codex-plugin/plugin.json", names)
        self.assertIn(root + ".mcp.json", names)
        self.assertIn(root + "skills/orbit/SKILL.md", names)
        self.assertNotIn("orbit-marketplace/.agents/plugins/marketplace.json", names)


if __name__ == "__main__":
    unittest.main()
