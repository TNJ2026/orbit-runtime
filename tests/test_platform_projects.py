"""Project discovery, runtime database paths and project indexing."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from promptaflow.platform import projects


class ProjectResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name).resolve()
        (self.root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        self.nested = self.root / "src" / "deep"
        self.nested.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_subdirectory_resolves_to_the_project_root(self) -> None:
        self.assertEqual(self.root, projects.resolve_project_root(self.nested))

    def test_unmarked_directory_resolves_to_itself(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            path = Path(bare).resolve()
            self.assertEqual(path, projects.resolve_project_root(path))

    def test_state_dir_is_the_current_name_and_ignores_dev_loop(self) -> None:
        """`.dev_loop` must not resurrect itself as a state directory."""

        (self.root / ".dev_loop").mkdir()
        self.assertEqual(
            self.root / ".promptaflow", projects.project_state_dir(self.root),
        )

    def test_an_existing_promptaflow_state_dir_is_used(self) -> None:
        (self.root / ".promptaflow").mkdir()
        self.assertEqual(
            self.root / ".promptaflow", projects.project_state_dir(self.root),
        )

    def test_project_id_is_stable_and_path_specific(self) -> None:
        first = projects.project_id(self.root)
        self.assertEqual(first, projects.project_id(self.nested.parent.parent))
        self.assertEqual(12, len(first))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as other:
            self.assertNotEqual(first, projects.project_id(other))


class RuntimeDatabasePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name).resolve()
        (self.root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        self.state = self.root / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_default_database_is_runtime_db(self) -> None:
        path = projects.project_db_path(self.root, base_dir=self.state)
        self.assertEqual("runtime.db", path.name)
        self.assertNotIn("messages.db", str(path))

    def test_same_leaf_name_does_not_collide(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as other_parent:
            twin = Path(other_parent) / self.root.name
            twin.mkdir()
            (twin / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            self.assertNotEqual(
                projects.project_db_path(self.root, base_dir=self.state),
                projects.project_db_path(twin, base_dir=self.state),
            )

    def test_path_is_stable_across_calls(self) -> None:
        self.assertEqual(
            projects.project_db_path(self.root, base_dir=self.state),
            projects.project_db_path(self.root, base_dir=self.state),
        )

class ProjectIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name).resolve()
        (self.root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        self.index = self.root / "index.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_upsert_replaces_the_entry_for_the_same_project(self) -> None:
        projects.upsert_project(
            project_root=self.root, db_path="/tmp/a.db", port=8848,
            index_path=self.index,
        )
        projects.upsert_project(
            project_root=self.root, db_path="/tmp/b.db", port=9999,
            index_path=self.index,
        )
        entries = json.loads(self.index.read_text(encoding="utf-8"))["projects"]
        self.assertEqual(1, len(entries))
        self.assertEqual("/tmp/b.db", entries[0]["db_path"])
        self.assertEqual(9999, entries[0]["port"])

    def test_online_probe_uses_the_runtime_readiness_endpoint(self) -> None:
        requested: list[str] = []

        class Response:
            status = 200

            def __enter__(self): return self
            def __exit__(self, *exc): return False

        def fake_urlopen(url, timeout=0.0):
            requested.append(url)
            return Response()

        with mock.patch.object(projects, "urlopen", fake_urlopen):
            online = projects.is_project_online({"server_url": "http://127.0.0.1:8848"})

        self.assertTrue(online)
        self.assertEqual(["http://127.0.0.1:8848/health/ready"], requested)

    def test_listing_marks_the_current_project_online_without_probing(self) -> None:
        projects.upsert_project(
            project_root=self.root, db_path="/tmp/a.db", index_path=self.index
        )
        identifier = projects.project_id(self.root)

        def refuse(_project):
            raise AssertionError("the current project must not be probed")

        listed = projects.list_projects(
            current_project_id=identifier,
            index_path=self.index,
            online_checker=refuse,
        )
        self.assertEqual(1, len(listed))
        self.assertTrue(listed[0]["current"])
        self.assertTrue(listed[0]["online"])


class PlatformBoundaryTests(unittest.TestCase):
    """M1A gate: the platform layer knows nothing about any engine."""

    def test_platform_does_not_import_engine_or_domain(self) -> None:
        import ast

        root = Path(projects.__file__).parent
        offenders: list[str] = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if any(
                        part in {"server", "store", "workflow"}
                        for part in name.split(".")
                    ):
                        offenders.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
