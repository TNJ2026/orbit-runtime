from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from promptaflow.web.builtin_handlers import builtin_handlers
from promptaflow.workflow.langgraph_runtime.compiler import (
    LangGraphExecutionContext, LangGraphUnknownExternalResult,
)
from promptaflow.workflow.langgraph_runtime.execution_worker import (
    ExecutionWorkerController, ExecutionWorkerPool,
    start_execution_worker, start_execution_worker_pool,
)


class ExecutionWorkerTests(unittest.TestCase):
    def test_controller_join_and_terminate_share_one_deadline(self) -> None:
        process = Mock()
        process.is_alive.side_effect = [True, True, True, False]
        worker = ExecutionWorkerController(process, ("127.0.0.1", 1), b"key", 7)
        worker.request = Mock(return_value={"ok": True})

        with patch(
            "promptaflow.workflow.langgraph_runtime.execution_worker.time.monotonic",
            side_effect=[10.0, 12.0, 14.0],
        ):
            self.assertTrue(worker.stop(timeout=5.0))

        self.assertEqual([call(timeout=3.0), call(timeout=1.0)], process.join.call_args_list)
        process.terminate.assert_called_once_with()

    def test_pool_stops_every_worker_with_the_remaining_budget(self) -> None:
        first = Mock()
        first.stop.return_value = False
        second = Mock()
        second.stop.return_value = True
        pool = ExecutionWorkerPool((first, second))

        with patch(
            "promptaflow.workflow.langgraph_runtime.execution_worker.time.monotonic",
            side_effect=[20.0, 21.0, 24.0],
        ):
            self.assertFalse(pool.stop(timeout=5.0))

        first.stop.assert_called_once_with(4.0)
        second.stop.assert_called_once_with(1.0)

    def test_pool_distributes_distinct_attempts_across_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, pool = start_execution_worker_pool(
                builtin_handlers(), state_directory=Path(temporary), worker_count=2,
            )
            self.addCleanup(pool.stop)
            handler = registry._entries["transform"]  # noqa: SLF001
            for index in (1, 2):
                handler.invoke(
                    {"index": index}, {},
                    LangGraphExecutionContext(
                        "workflow:test", "transform", "langgraph_run:test",
                        f"langgraph_attempt:test:transform:{index}",
                    ),
                )

            self.assertEqual(2, len(set(pool.pids)))
            self.assertEqual(
                2,
                len({worker.pid for worker in pool._attempt_workers.values()}),  # noqa: SLF001
            )

    def test_handler_execution_runs_in_a_separate_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, worker = start_execution_worker(
                builtin_handlers(), state_directory=Path(temporary),
            )
            self.addCleanup(worker.stop)
            handler = registry._entries["transform"]  # noqa: SLF001

            output = handler.invoke(
                {"answer": 42}, {"operation": "identity"},
                LangGraphExecutionContext(
                    "workflow:test", "transform", "langgraph_run:test",
                    "langgraph_attempt:test:transform:1",
                ),
            )

            self.assertEqual({"answer": 42}, output)
            self.assertNotEqual(os.getpid(), worker.pid)
            self.assertTrue(worker.alive)

    def test_a_non_protocol_connection_does_not_kill_the_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, worker = start_execution_worker(
                builtin_handlers(), state_directory=Path(temporary),
            )
            self.addCleanup(worker.stop)

            with socket.create_connection(worker.address) as connection:
                connection.sendall(
                    b"GET /health/ready HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
                )

            handler = registry._entries["transform"]  # noqa: SLF001
            output = handler.invoke(
                {"answer": 42}, {"operation": "identity"},
                LangGraphExecutionContext(
                    "workflow:test", "transform", "langgraph_run:test",
                    "langgraph_attempt:test:transform:malformed-peer",
                ),
            )
            self.assertEqual({"answer": 42}, output)
            self.assertTrue(worker.alive)

    def test_worker_loss_is_reported_as_an_unknown_external_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry, worker = start_execution_worker(
                builtin_handlers(), state_directory=Path(temporary),
            )
            handler = registry._entries["transform"]  # noqa: SLF001
            self.assertTrue(worker.stop())

            with self.assertRaisesRegex(
                LangGraphUnknownExternalResult, "Worker is unavailable",
            ):
                handler.invoke(
                    {"answer": 42}, {},
                    LangGraphExecutionContext(
                        "workflow:test", "transform", "langgraph_run:test",
                        "langgraph_attempt:test:transform:1",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
