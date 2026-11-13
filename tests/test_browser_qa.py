from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import browser_qa


class BrowserQAContractTests(unittest.TestCase):
    def test_matrix_topology_is_exact(self) -> None:
        self.assertEqual(288, 36 * len(browser_qa.MODES) * len(browser_qa.VIEWPORTS))
        self.assertEqual(16, len(browser_qa.REFERENCE_PRESETS) * len(browser_qa.MODES) * len(browser_qa.SCREENSHOT_VIEWPORTS))
        self.assertEqual(20, browser_qa.COLD_READINESS_SAMPLES)
        self.assertEqual(5, browser_qa.THEME_SWITCH_WARMUPS)
        self.assertEqual(100, browser_qa.THEME_SWITCH_SAMPLES)

    def test_selected_driver_is_exactly_stdlib_cdp(self) -> None:
        record = json.loads(browser_qa.DRIVER_RECORD.read_text(encoding="utf-8"))
        self.assertEqual("stdlib-cdp", record["selected_driver"])
        self.assertEqual(["stdlib-cdp"], record["implementations"])
        self.assertEqual(8, len(record["feasibility"]["primitives"]))
        self.assertTrue(all(item["status"] == "pass" for item in record["feasibility"]["primitives"].values()))

    def test_driver_validation_fails_closed_on_browser_drift(self) -> None:
        with mock.patch.object(browser_qa, "chromium_version", side_effect=browser_qa.QAError("drift")):
            with self.assertRaisesRegex(browser_qa.QAError, "drift"):
                browser_qa.validate_driver_record()

    def test_structural_case_ids_are_stable(self) -> None:
        client = mock.Mock()
        client.evaluate.return_value = {
            "preset": "graphite", "mode": "light", "viewport": [320, 800],
            "pageWidth": 320, "clientWidth": 320, "clipped": [], "intersections": [],
            "tableContained": True, "controls": {
                "theme": {"visible": {"w": 100}, "name": "Preset"},
                "light": {"visible": {"w": 50}, "name": "Light"},
                "dark": {"visible": {"w": 50}, "name": "Dark"},
            }, "tokens": {"background": "white", "foreground": "black", "primary": "blue"},
        }
        item = browser_qa.structural_record(client, "graphite", "light", 320, 800)
        self.assertEqual("structural/graphite/light/320x800", item["id"])
        self.assertEqual([], item["errors"])
        self.assertRegex(item["hash"], r"^[0-9a-f]{64}$")

    def test_missing_driver_record_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(browser_qa, "DRIVER_RECORD", Path(directory) / "missing.json"):
                with self.assertRaisesRegex(browser_qa.QAError, "invalid selected-driver record"):
                    browser_qa.validate_driver_record()

    def test_visual_verdict_matrix_is_complete(self) -> None:
        verdicts = browser_qa.load_visual_verdicts()
        expected = {
            f"visual/{preset}/{mode}/{width}x{height}"
            for preset in browser_qa.REFERENCE_PRESETS
            for mode in browser_qa.MODES
            for width, height in browser_qa.SCREENSHOT_VIEWPORTS
        }
        self.assertEqual(expected, set(verdicts))

    def test_cleanup_failure_is_blocking(self) -> None:
        client = object.__new__(browser_qa.CDPClient)
        client._closed = False
        client._writer = mock.Mock()
        client._reader = mock.Mock()
        client.process = mock.Mock()
        client.process.poll.return_value = 0
        client.profile = Path("/tmp/theme-forge-cleanup-contract")
        with mock.patch.object(browser_qa.shutil, "rmtree", side_effect=OSError("busy")):
            with self.assertRaisesRegex(browser_qa.QAError, "profile cleanup failed"):
                client.close()

    def test_context_manager_does_not_hide_cleanup_failure(self) -> None:
        client = object.__new__(browser_qa.CDPClient)
        client.close = mock.Mock(side_effect=browser_qa.QAError("cleanup failed"))
        with self.assertRaisesRegex(browser_qa.QAError, "cleanup failed"):
            client.__exit__(None, None, None)

    def test_baseline_promotion_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture, baseline = root / "capture.png", root / "baseline.png"
            capture.write_bytes(b"capture")
            self.assertEqual(0, browser_qa.promote_baselines([(capture, baseline)], ["visual fail"]))
            self.assertFalse(baseline.exists())
            self.assertEqual(1, browser_qa.promote_baselines([(capture, baseline)], []))
            self.assertEqual(b"capture", baseline.read_bytes())


if __name__ == "__main__":
    unittest.main()
