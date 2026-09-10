from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from promptaflow.workflow.handlers.agent import _agent_result
from promptaflow.workflow.handlers.deliverables import linked_files, read_deliverables
from promptaflow.workflow.langgraph_runtime import build_service
from promptaflow.workflow.langgraph_runtime.artifacts import LangGraphArtifactStore
from tests.test_web_composition import publish_linear_workflow, transform_registration


class DeliverableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "deck.pptx").write_bytes(b"pptx bytes")
        (self.workspace / "preview.pdf").write_bytes(b"pdf bytes")
        self.store = LangGraphArtifactStore(self.root / "runs.db", self.root / "blobs")

    def access(self):
        return self.store.access(run_id="run", node_id="node", attempt_id="attempt",
                                 output_ports=(), inputs={}, actor="alice")

    def test_only_explicit_local_links_are_candidates(self):
        text = "[deck](deck.pptx) [pdf](<preview.pdf>) [web](https://example.com/x.pdf) [dir](previews/) [again](deck.pptx)"
        self.assertEqual(("deck.pptx", "preview.pdf"), linked_files(text, self.workspace))

    def test_cli_result_publishes_attachments_even_for_inline_port(self):
        access = self.access()
        context = SimpleNamespace(artifacts=access, deliverable_workspace=self.workspace,
                                  request=SimpleNamespace(output_ports=()))
        response = _agent_result("[PPT](deck.pptx) [PDF](preview.pdf)", context)
        self.assertEqual(2, len(response.artifact_refs))
        self.assertEqual(set(response.artifact_refs), set(access.produced_artifact_ids))
        self.assertEqual((), self.store.list(run_id="run"))
        access.commit()
        files = self.store.list(run_id="run", actor="alice")
        self.assertEqual({"deck.pptx", "preview.pdf"}, {f["filename"] for f in files})
        self.assertEqual((), self.store.list(run_id="run", actor="bob"))
        for item in files:
            self.assertEqual((self.workspace / item["filename"]).read_bytes(), self.store.read(item["artifact_id"], actor="alice"))

    def test_bad_paths_cannot_publish_private_files(self):
        (self.workspace / "link.pdf").symlink_to(self.workspace / "preview.pdf")
        (self.workspace / ".private.pdf").write_bytes(b"private")
        for path in ("../preview.pdf", ".private.pdf", "link.pdf", str(self.workspace / "preview.pdf")):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                read_deliverables(self.workspace, [path])

    def test_parent_symlink_and_size_limit_are_rejected(self):
        (self.workspace / "alias").symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises(OSError):
            read_deliverables(self.workspace, ["alias/preview.pdf"])
        with patch("promptaflow.workflow.handlers.deliverables.MAX_FILE_BYTES", 2):
            with self.assertRaises(ValueError):
                read_deliverables(self.workspace, ["preview.pdf"])

    def test_real_cli_publishes_from_its_actual_cwd(self):
        from tests.test_agent_prompt_cli import FakeCli
        from promptaflow.workflow.handlers.agent import AgentRequest, TrustedPromptCliAgentClient

        cli = FakeCli("from pathlib import Path\nPath('deck.pptx').write_bytes(b'generated')\nprint('[PPT](deck.pptx)')")
        self.addCleanup(cli.cleanup)
        access = self.access()
        client = TrustedPromptCliAgentClient((str(cli.path),), workspace_root=self.workspace)
        response = client.execute(AgentRequest({"prompt": "make a deck"}, {}, "key"),
            SimpleNamespace(artifacts=access, request=SimpleNamespace(
                attempt_id="attempt", run_id="run", input_ports=(), output_ports=()),
            ))
        self.assertEqual(1, len(response.artifact_refs))
        access.commit()
        self.assertEqual(b"generated", self.store.read(response.artifact_refs[0]))

    def test_bad_batch_never_partially_stages(self):
        access = self.access()
        with self.assertRaises(ValueError):
            access.publish_files(self.workspace, ["deck.pptx", "missing.pdf"])
        self.assertEqual((), access.produced_artifact_ids)

    def test_missing_link_reports_delivery_failure_without_reexecution(self):
        response = _agent_result("[PDF](missing.pdf)", SimpleNamespace(
            artifacts=self.access(), deliverable_workspace=self.workspace,
            request=SimpleNamespace(output_ports=()),
        ))
        self.assertIn("File publication failed", response.output["result"]["text"])
        self.assertEqual((), response.artifact_refs)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        db = self.root / "runtime.db"
        publish_linear_workflow(db)
        self.service = build_service(db, [transform_registration()], state_directory=self.root / "state")
        self.run = self.service.start("workflow:linear", {"value": 1}, idempotency_key="start", actor="alice")
        self.service.project_access = SimpleNamespace(project_root=self.root)
        self.need = patch("promptaflow.workflow.langgraph_runtime.project_access.project_access_need", return_value=True)
        self.need.start()
        self.addCleanup(self.need.stop)
        (self.root / "deck.pptx").write_bytes(b"pptx")

    def publish(self, **kwargs):
        return self.service.publish_run_files(self.run.run_id, ["deck.pptx"],
            expected_revision=self.run.revision, idempotency_key="repair", **kwargs)

    def test_repair_is_idempotent_preserves_result_and_updates_count(self):
        fixed = self.publish(actor="alice")
        self.assertEqual(self.run.result, fixed.result)
        self.assertEqual("completed", fixed.status)
        self.assertEqual(self.run.revision + 1, fixed.revision)
        self.assertEqual(1, fixed.artifact_count)
        self.assertEqual(fixed, self.publish(actor="alice"))
        self.assertEqual(1, self.service.list_runs(actor="alice")[0].artifact_count)

    def test_other_actor_cannot_repair_or_replay_receipt(self):
        self.publish(actor="alice")
        with self.assertRaises(LookupError):
            self.publish(actor="bob")

    def test_stale_revision_does_not_publish(self):
        self.publish(actor="alice")
        with self.assertRaises(ValueError):
            self.service.publish_run_files(self.run.run_id, ["deck.pptx"],
                expected_revision=self.run.revision, idempotency_key="another", actor="alice")
        self.assertEqual(1, self.service.get(self.run.run_id).artifact_count)
