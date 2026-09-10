"""Real browser interactions against the shipped UI, with simulated job responses."""
from tests.test_browser_e2e import BrowserE2ETestCase


class GenerationDialogTests(BrowserE2ETestCase):
    @classmethod
    def extra_app_kwargs(cls):
        return {"workflow_generator": lambda _: "unused"}

    def dialog_fixture(self):
        page = self.open("en-US", "/ui/#/workflows")

        def catalog(route):
            response = route.fetch()
            payload = response.json()
            entry = payload["data"]["workflows"][0]
            entry["goal_readiness"] = "needs_migration"
            entry["goal_binding"] = None
            route.fulfill(response=response, json=payload)

        page.route("**/api/v1/workflows", catalog)
        page.reload()
        page.locator(".workflow-card-actions").get_by_role("button", name="Generate workflow").first.click()
        dialog = page.locator(".workflow-generation-dialog")
        dialog.wait_for()
        state = {"status": "queued"}
        pending = []

        def job():
            return {
                "job_id": "close-test", "href": "/api/v1/authoring-jobs/close-test",
                "status": state["status"], "prompt": "test workflow",
                "allowed_commands": [{
                    "command": "workflow.authoring.cancel", "method": "POST",
                    "href": "/api/v1/authoring-jobs/close-test/cancel", "expected_version": 1,
                }] if state["status"] in ("queued", "running") else [],
            }

        page.route("**/api/v1/workflows/generate", lambda route: pending.append(route))
        page.route("**/api/v1/authoring-jobs/close-test", lambda route: route.fulfill(json={"data": job()}))

        def cancel(route):
            state["status"] = "cancelled"
            route.fulfill(json={"data": job()})

        page.route("**/api/v1/authoring-jobs/close-test/cancel", cancel)
        return page, dialog, state, pending, job

    def test_close_is_locked_during_submission_and_running_then_shown_for_all_outcomes(self):
        for status in ("done", "failed", "cancelled"):
            with self.subTest(status=status):
                page, dialog, state, pending, job = self.dialog_fixture()
                close = dialog.locator(".workflow-generation-dialog-close")
                self.assertTrue(close.is_visible())
                dialog.locator("#generateInstruction").fill("test workflow")
                dialog.locator("#generateSubmit").click()
                close.wait_for(state="hidden")
                page.keyboard.press("Escape")
                self.assertTrue(dialog.is_visible())
                page.wait_for_timeout(50)
                self.assertEqual(1, len(pending))
                pending[0].fulfill(json={"data": job()})
                dialog.locator(".authoring-job-state.queued").wait_for()
                self.assertFalse(close.is_visible())
                state["status"] = "running"
                dialog.locator(".authoring-job-state.running").wait_for()
                page.keyboard.press("Escape")
                self.assertTrue(dialog.is_visible())
                self.assertFalse(close.is_visible())
                if status == "cancelled":
                    dialog.get_by_role("button", name="Cancel", exact=True).click()
                else:
                    state["status"] = status
                close.wait_for(state="visible")
                page.keyboard.press("Escape")
                self.assertTrue(dialog.is_visible())
                close.hover()
                page.wait_for_function("""() => {
                    const node = document.querySelector('.workflow-generation-dialog-close');
                    return node && getComputedStyle(node).backgroundColor !== 'rgba(0, 0, 0, 0)';
                }""")
                color = close.evaluate("node => getComputedStyle(node).backgroundColor")
                self.assertNotIn(color, ("rgba(0, 0, 0, 0)", "transparent"))
                box = close.bounding_box()
                panel = dialog.bounding_box()
                self.assertGreaterEqual(box["x"], panel["x"] + 16)
                self.assertLessEqual(box["x"] + box["width"], panel["x"] + panel["width"] - 16)
                close.click()
                dialog.wait_for(state="detached")

    def test_failed_submission_restores_close_but_escape_stays_disabled(self):
        page, dialog, _, pending, _ = self.dialog_fixture()
        dialog.locator("#generateInstruction").fill("test workflow")
        dialog.locator("#generateSubmit").click()
        page.wait_for_timeout(50)
        pending[0].fulfill(status=503, json={"error": {"code": "unavailable", "message": "offline"}})
        close = dialog.locator(".workflow-generation-dialog-close")
        close.wait_for(state="visible")
        page.keyboard.press("Escape")
        self.assertTrue(dialog.is_visible())
        close.click()
        dialog.wait_for(state="detached")
