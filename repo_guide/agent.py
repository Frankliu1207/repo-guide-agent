import os
from pathlib import Path

from smolagents import InferenceClientModel, Tool, ToolCallingAgent, tool

from repo_guide.repository import (
    list_project_files as list_safe_project_files,
    read_project_file as read_safe_project_file,
    validate_repository_path,
)


DEFAULT_MODEL_ID = "openai/gpt-oss-120b"

AGENT_INSTRUCTIONS = """
你是面向编程初学者的安全仓库导览 Agent。
开始分析前必须先调用 list_project_files，了解允许查看的文件。
只在确有必要时调用 read_project_file，并且只读取完成回答所需的少量文件。
不要猜测没有文件依据的内容；证据不足时明确说明。

最终使用中文回答，并包含：
1. 项目用途和主要技术栈。
2. 可能的入口文件。
3. 初学者推荐阅读顺序。
4. 初学者下一步可以做什么。
5. 判断依据，列出实际读取过的相对文件路径。

信息足够后必须调用 final_answer 工具提交完整答案。
不要直接输出普通文本，也不要输出只有 answer 字段的 JSON。
最终答案尽量控制在 800 个中文字符以内，避免重复内容。
""".strip()


def create_repository_tools(repository_path: str | Path) -> list[Tool]:
    """Create two smolagents tools bound to one validated repository."""
    repository_root = validate_repository_path(repository_path)

    @tool
    def list_project_files() -> str:
        """List safe text and source files in the selected repository."""
        return list_safe_project_files(repository_root)

    @tool
    def read_project_file(relative_path: str) -> str:
        """Read one safe text file from the selected repository.

        Args:
            relative_path: A repository-relative path returned by list_project_files.
        """
        try:
            return read_safe_project_file(repository_root, relative_path)
        except ValueError as error:
            return f"读取被拒绝：{error}"

    return [list_project_files, read_project_file]


def build_repository_agent(
    repository_path: str | Path,
    model_id: str = DEFAULT_MODEL_ID,
    provider: str = "auto",
    max_steps: int = 8,
) -> ToolCallingAgent:
    """Build a ToolCallingAgent with two repository-scoped read-only tools."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("缺少 HF_TOKEN，请先在当前终端设置 Hugging Face Token")

    model = InferenceClientModel(model_id=model_id, provider=provider, token=token)
    tools = create_repository_tools(repository_path)

    return ToolCallingAgent(
        tools=tools,
        model=model,
        instructions=AGENT_INSTRUCTIONS,
        max_steps=max_steps,
        verbosity_level=2,
    )
