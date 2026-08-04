import argparse
import os
import re
import sys
from collections.abc import Sequence

from repo_guide.agent import build_repository_agent


HF_TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{10,}")


def parse_max_steps(value: str) -> int:
    """Parse a bounded Agent step count for the command line."""
    max_steps = int(value)
    if not 1 <= max_steps <= 20:
        raise argparse.ArgumentTypeError("必须在 1 到 20 之间")
    return max_steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用安全只读工具生成中文仓库导览")
    parser.add_argument("--repo", required=True, help="需要分析的本地 Git 仓库路径")
    parser.add_argument("--question", required=True, help="希望 Agent 回答的问题")
    parser.add_argument("--max-steps", type=parse_max_steps, default=8, help="Agent 最大步骤数，默认 8")
    return parser


def redact_secrets(message: str) -> str:
    """Remove the current token and token-shaped strings from an error message."""
    token = os.environ.get("HF_TOKEN")
    if token:
        message = message.replace(token, "[REDACTED]")
    return HF_TOKEN_PATTERN.sub("[REDACTED]", message)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        agent = build_repository_agent(args.repo, max_steps=args.max_steps)
        result = agent.run(args.question)
    except (RuntimeError, ValueError) as error:
        print(f"错误：{redact_secrets(str(error))}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Agent 运行失败：{redact_secrets(str(error))}", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
