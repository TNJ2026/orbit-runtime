"""Where state lives across the rename, and when it is allowed to move."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from promptaflow import paths


class HomeRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = patch.object(Path, "home", staticmethod(lambda: self.home))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_fresh_install_uses_the_current_name(self) -> None:
        self.assertEqual(self.home / ".promptaflow", paths.home_root())

    def test_an_existing_legacy_root_is_read_without_migrating(self) -> None:
        (self.home / ".orbit").mkdir()
        self.assertEqual(self.home / ".orbit", paths.home_root())

    def test_the_current_name_wins_when_both_exist(self) -> None:
        (self.home / ".orbit").mkdir()
        (self.home / ".promptaflow").mkdir()
        self.assertEqual(self.home / ".promptaflow", paths.home_root())


class HomeMigrationTests(HomeRootTests):
    def test_nothing_to_move_is_not_an_event(self) -> None:
        result = paths.migrate_home_root()
        self.assertIsNone(result.moved_to)
        self.assertEqual((), result.blocked_by)

    def test_a_quiet_legacy_root_is_moved_once(self) -> None:
        (self.home / ".orbit").mkdir()
        (self.home / ".orbit" / "projects").mkdir()
        with patch.object(paths, "_live_under", return_value=()):
            result = paths.migrate_home_root()
        self.assertEqual(self.home / ".promptaflow", result.moved_to)
        self.assertTrue((self.home / ".promptaflow" / "projects").is_dir())
        self.assertFalse((self.home / ".orbit").exists())

        # Idempotent: the second run has nothing left to do.
        with patch.object(paths, "_live_under", return_value=()):
            self.assertIsNone(paths.migrate_home_root().moved_to)

    def test_a_root_a_runtime_is_using_is_left_alone(self) -> None:
        """`rename` would succeed and break every one of them silently."""

        (self.home / ".orbit").mkdir()
        with patch.object(paths, "_live_under", return_value=("http://127.0.0.1:1",)):
            result = paths.migrate_home_root()
        self.assertIsNone(result.moved_to)
        self.assertEqual(("http://127.0.0.1:1",), result.blocked_by)
        self.assertTrue((self.home / ".orbit").is_dir())
        self.assertEqual(self.home / ".orbit", paths.home_root())

    def test_discovery_that_cannot_answer_blocks_rather_than_guesses(self) -> None:
        (self.home / ".orbit").mkdir()
        with patch(
            "promptaflow.platform.runtime_ownership.discover_runtimes",
            side_effect=OSError("no"),
        ):
            result = paths.migrate_home_root()
        self.assertIsNone(result.moved_to)
        self.assertTrue((self.home / ".orbit").is_dir())


class ProjectStateDirTests(HomeRootTests):
    def test_a_directory_in_the_user_repository_is_read_never_moved(self) -> None:
        project = self.home / "repo"
        (project / ".orbit").mkdir(parents=True)
        self.assertEqual(project / ".orbit", paths.project_state_dir(project))
        self.assertTrue((project / ".orbit").is_dir())


class CliMigrationTests(unittest.TestCase):
    """The CLI moves the root once, then stops rather than running on it."""

    def test_the_first_run_migrates_and_asks_to_be_run_again(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            home = Path(temporary)
            (home / ".orbit" / "projects").mkdir(parents=True)
            environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}

            first = subprocess.run(
                [sys.executable, "-m", "promptaflow", "--version"],
                capture_output=True, text=True, env=environment, timeout=60,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertIn("Run the command again", first.stderr)
            self.assertNotIn("promptaflow 2", first.stdout)
            self.assertTrue((home / ".promptaflow" / "projects").is_dir())
            self.assertFalse((home / ".orbit").exists())

            # And the run after it is an ordinary one.
            second = subprocess.run(
                [sys.executable, "-m", "promptaflow", "--version"],
                capture_output=True, text=True, env=environment, timeout=60,
            )
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertIn("promptaflow", second.stdout)
            self.assertNotIn("Run the command again", second.stderr)


if __name__ == "__main__":
    unittest.main()
