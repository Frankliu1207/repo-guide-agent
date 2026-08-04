import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

import app


class AppTests(unittest.TestCase):
    @patch("app.build_repository_agent")
    def test_runs_agent_and_prints_result(self, build_agent: Mock) -> None:
        agent = Mock()
        agent.run.return_value = "中文仓库导览"
        build_agent.return_value = agent
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = app.main(["--repo", "example-repo", "--question", "这个项目做什么？"])

        self.assertEqual(exit_code, 0)
        build_agent.assert_called_once_with("example-repo", max_steps=8)
        agent.run.assert_called_once_with("这个项目做什么？")
        self.assertEqual(stdout.getvalue().strip(), "中文仓库导览")

    @patch("app.build_repository_agent", side_effect=RuntimeError("缺少 HF_TOKEN"))
    def test_returns_clear_error_for_expected_failure(self, _build_agent: Mock) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            exit_code = app.main(["--repo", "example-repo", "--question", "问题"])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr.getvalue().strip(), "错误：缺少 HF_TOKEN")

    @patch("app.build_repository_agent")
    def test_redacts_token_from_unexpected_error(self, build_agent: Mock) -> None:
        token = "hf_" + "abcdefghijklmnopqrstuvwxyz123456"
        build_agent.side_effect = Exception(f"provider rejected {token}")
        stderr = io.StringIO()

        with patch.dict(os.environ, {"HF_TOKEN": token}), redirect_stderr(stderr):
            exit_code = app.main(["--repo", "example-repo", "--question", "问题"])

        self.assertEqual(exit_code, 1)
        self.assertNotIn(token, stderr.getvalue())
        self.assertIn("[REDACTED]", stderr.getvalue())

    def test_rejects_out_of_range_max_steps(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
            app.main(["--repo", "example-repo", "--question", "问题", "--max-steps", "21"])

        self.assertEqual(error.exception.code, 2)
        self.assertIn("必须在 1 到 20 之间", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
