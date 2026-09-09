"""PromptaFlow uses one canonical state namespace."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from promptaflow import paths


class StatePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = patch.object(Path, "home", staticmethod(lambda: self.home))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_root_is_promptaflow(self) -> None:
        self.assertEqual(self.home / ".promptaflow", paths.home_root())

    def test_home_root_does_not_depend_on_existing_directories(self) -> None:
        (self.home / ".promptaflow").mkdir()
        self.assertEqual(self.home / ".promptaflow", paths.home_root())

    def test_project_state_dir_is_promptaflow(self) -> None:
        project = self.home / "repo"
        project.mkdir()
        self.assertEqual(project / ".promptaflow", paths.project_state_dir(project))


if __name__ == "__main__":
    unittest.main()
