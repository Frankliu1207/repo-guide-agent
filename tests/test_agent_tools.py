import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_guide.agent import AGENT_INSTRUCTIONS, build_repository_agent, create_repository_tools


class RepositoryAgentToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_path = Path(self.temporary_directory.name)
        (self.repository_path / ".git").mkdir()
        (self.repository_path / "README.md").write_text("项目说明", encoding="utf-8")
        (self.repository_path / ".env").write_text("SECRET=value", encoding="utf-8")

        tools = create_repository_tools(self.repository_path)
        self.tools_by_name = {tool.name: tool for tool in tools}

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_creates_exactly_two_named_tools(self) -> None:
        self.assertEqual(set(self.tools_by_name), {"list_project_files", "read_project_file"})

    def test_list_tool_returns_safe_relative_paths(self) -> None:
        result = self.tools_by_name["list_project_files"]()

        self.assertEqual(result, "README.md")

    def test_read_tool_returns_text_and_rejects_sensitive_file(self) -> None:
        read_tool = self.tools_by_name["read_project_file"]

        self.assertEqual(read_tool(relative_path="README.md"), "项目说明")
        self.assertEqual(read_tool(relative_path=".env"), "读取被拒绝：禁止读取敏感文件")


class BuildRepositoryAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_path = Path(self.temporary_directory.name)
        (self.repository_path / ".git").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_requires_hf_token(self) -> None:
        with patch.dict(os.environ, {"HF_TOKEN": ""}):
            with self.assertRaisesRegex(RuntimeError, "缺少 HF_TOKEN"):
                build_repository_agent(self.repository_path)

    def test_instructions_require_final_answer_tool_and_evidence(self) -> None:
        self.assertIn("必须调用 final_answer 工具", AGENT_INSTRUCTIONS)
        self.assertIn("实际读取过的相对文件路径", AGENT_INSTRUCTIONS)
        self.assertIn("800 个中文字符以内", AGENT_INSTRUCTIONS)

    @patch("repo_guide.agent.ToolCallingAgent")
    @patch("repo_guide.agent.InferenceClientModel")
    def test_builds_tool_calling_agent_without_network_request(
        self,
        model_class,
        agent_class,
    ) -> None:
        expected_agent = object()
        model_instance = object()
        model_class.return_value = model_instance
        agent_class.return_value = expected_agent

        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            result = build_repository_agent(self.repository_path)

        self.assertIs(result, expected_agent)
        model_class.assert_called_once_with(
            model_id="openai/gpt-oss-120b",
            provider="auto",
            token="hf_test_token",
        )

        agent_arguments = agent_class.call_args.kwargs
        self.assertEqual(len(agent_arguments["tools"]), 2)
        self.assertIs(agent_arguments["model"], model_instance)
        self.assertEqual(agent_arguments["instructions"], AGENT_INSTRUCTIONS)
        self.assertEqual(agent_arguments["max_steps"], 8)
        self.assertEqual(agent_arguments["verbosity_level"], 2)


if __name__ == "__main__":
    unittest.main()
