from pathlib import Path

def validate_repository_path(repo_path: str | Path) -> Path:
    path = Path(repo_path)
    if not path.exists():
        raise ValueError("Repository path does not exist")
    if not path.is_dir():
        raise ValueError("Repository path is not a directory")
    return path
import os
from pathlib import Path


BLOCKED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}

BLOCKED_FILE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
}

BLOCKED_PRIVATE_KEY_SUFFIXES = {
    ".key",
    ".p12",
    ".pem",
    ".pfx",
}

ALLOWED_TEXT_SUFFIXES = {
    ".c",
    ".cpp",
    ".css",
    ".gradle",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".kts",
    ".md",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

ALLOWED_SPECIAL_TEXT_FILE_NAMES = {
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitignore",
    "dockerfile",
    "license",
    "makefile",
    "readme",
}

DEFAULT_MAX_RETURN_CHARS = 6_000
DEFAULT_MAX_FILE_BYTES = 256_000
DEFAULT_MAX_LIST_DEPTH = 4
DEFAULT_MAX_LIST_FILES = 120


def validate_repository_path(repo_path: str | Path) -> Path:
    """Validate a repository path and return its resolved absolute path."""
    candidate = Path(repo_path).expanduser()

    if not candidate.exists():
        raise ValueError("仓库路径不存在")

    resolved_path = candidate.resolve()

    if not resolved_path.is_dir():
        raise ValueError("仓库路径不是目录")

    if not (resolved_path / ".git").exists():
        raise ValueError("目标不是 Git 仓库")

    return resolved_path


def resolve_repository_path(repository_path: str | Path, relative_path: str | Path) -> Path:
    """Resolve a relative path while keeping it inside the target repository."""
    repository_root = validate_repository_path(repository_path)
    requested_path = Path(relative_path)

    if requested_path.is_absolute():
        raise ValueError("只允许仓库内的相对路径")

    resolved_path = (repository_root / requested_path).resolve()

    try:
        resolved_path.relative_to(repository_root)
    except ValueError as error:
        raise ValueError("禁止访问仓库外路径") from error

    return resolved_path


def validate_safe_file_path(repository_path: str | Path, relative_path: str | Path) -> Path:
    """Reject sensitive repository paths before any file is opened."""
    repository_root = validate_repository_path(repository_path)
    resolved_path = resolve_repository_path(repository_root, relative_path)
    repository_parts = resolved_path.relative_to(repository_root).parts

    if any(part.lower() in BLOCKED_DIRECTORY_NAMES for part in repository_parts):
        raise ValueError("禁止访问敏感目录")

    file_name = resolved_path.name.lower()
    is_environment_file = file_name == ".env" or (
        file_name.startswith(".env.") and file_name != ".env.example"
    )

    if (
        file_name in BLOCKED_FILE_NAMES
        or is_environment_file
        or resolved_path.suffix.lower() in BLOCKED_PRIVATE_KEY_SUFFIXES
    ):
        raise ValueError("禁止读取敏感文件")

    return resolved_path


def read_project_file(
    repository_path: str | Path,
    relative_path: str | Path,
    max_chars: int = DEFAULT_MAX_RETURN_CHARS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> str:
    """Read a bounded UTF-8 text file after applying repository safety checks."""
    resolved_path = validate_safe_file_path(repository_path, relative_path)

    if not resolved_path.exists():
        raise ValueError("文件不存在")

    if not resolved_path.is_file():
        raise ValueError("目标不是普通文件")

    file_name = resolved_path.name.lower()
    suffix = resolved_path.suffix.lower()
    if suffix not in ALLOWED_TEXT_SUFFIXES and file_name not in ALLOWED_SPECIAL_TEXT_FILE_NAMES:
        raise ValueError("不允许读取该文件类型")

    if resolved_path.stat().st_size > max_file_bytes:
        raise ValueError("文件过大，拒绝读取")

    file_bytes = resolved_path.read_bytes()
    if b"\x00" in file_bytes:
        raise ValueError("检测到二进制文件，拒绝读取")

    try:
        content = file_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("文件不是有效的 UTF-8 文本") from error

    if len(content) <= max_chars:
        return content

    truncation_marker = "\n\n[内容已截断]"
    visible_characters = max(0, max_chars - len(truncation_marker))
    return content[:visible_characters] + truncation_marker


def list_project_files(
    repository_path: str | Path,
    max_depth: int = DEFAULT_MAX_LIST_DEPTH,
    max_files: int = DEFAULT_MAX_LIST_FILES,
) -> str:
    """List a bounded set of safe text files using repository-relative paths."""
    if max_depth < 0:
        raise ValueError("目录深度不能小于 0")
    if max_files < 1:
        raise ValueError("文件数量上限必须大于 0")

    repository_root = validate_repository_path(repository_path)
    listed_files: list[str] = []

    for current_directory, directory_names, file_names in os.walk(repository_root, followlinks=False):
        current_path = Path(current_directory)
        relative_directory = current_path.relative_to(repository_root)
        current_depth = 0 if relative_directory == Path(".") else len(relative_directory.parts)

        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if directory_name.lower() not in BLOCKED_DIRECTORY_NAMES and current_depth < max_depth
        )

        if current_depth > max_depth:
            continue

        for file_name in sorted(file_names):
            relative_path = (relative_directory / file_name) if relative_directory != Path(".") else Path(file_name)

            try:
                safe_path = validate_safe_file_path(repository_root, relative_path)
            except ValueError:
                continue

            normalized_name = safe_path.name.lower()
            if (
                safe_path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES
                and normalized_name not in ALLOWED_SPECIAL_TEXT_FILE_NAMES
            ):
                continue

            listed_files.append(relative_path.as_posix())
            if len(listed_files) == max_files:
                listed_files.append(f"[文件列表已截断，最多显示 {max_files} 个文件]")
                return "\n".join(listed_files)

    if not listed_files:
        return "[没有可显示的文本文件]"

    return "\n".join(listed_files)
