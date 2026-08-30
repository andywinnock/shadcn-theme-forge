import subprocess
import unittest
from unittest import mock

import verify_release


class ReleaseRunnerTests(unittest.TestCase):
    def test_pyright_and_required_qualification_stages_are_present(self):
        stages = {stage.name: stage for stage in verify_release.release_stages()}
        self.assertIn("pyright", stages)
        self.assertEqual(stages["pyright"].command[0], "pyright")
        self.assertIn("native-matrix", stages)
        self.assertIn("native-qt", stages)
        self.assertIn("native-noctalia", stages)
        self.assertNotIn("--apply", stages["native-qt"].command)
        self.assertIn("browser-qa", stages)
        self.assertIn("noctalia-config", stages)

    @mock.patch("verify_release.shutil.which", return_value="/usr/bin/tool")
    @mock.patch("verify_release.subprocess.run")
    def test_stage_preserves_failure_exit_code(self, run, _which):
        run.return_value = subprocess.CompletedProcess([], 23, "partial", "failed")
        result = verify_release.run_stage(verify_release.Stage("gate", ("tool",)))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.returncode, 23)

    @mock.patch("verify_release.shutil.which", return_value="/usr/bin/tool")
    @mock.patch("verify_release.subprocess.run", side_effect=subprocess.TimeoutExpired("tool", 1))
    def test_stage_timeout_is_blocking(self, _run, _which):
        result = verify_release.run_stage(verify_release.Stage("gate", ("tool",), 1))
        self.assertEqual(result.returncode, 124)
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
