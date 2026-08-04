import tempfile
import unittest
from pathlib import Path

from repo_guide.repository import (
    list_project_files,
    read_project_file,
    resolve_repository_path,
    validate_repository_path,
    validate_safe_file_path,
)


class ValidateRepositoryPathTests(unittest.TestCase):
    def test_accepts_git_repository_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_path = Path(temporary_directory)
            (repository_path / ".git").mkdir()

            result = validate_repository_path(repository_path)

            self.assertEqual(result, repository_path.resolve())

    def test_rejects_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing"

            with self.assertRaisesRegex(ValueError, "仓库路径不存在"):
                validate_repository_path(missing_path)

    def test_rejects_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "README.md"
            file_path.write_text("example", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "仓库路径不是目录"):
                validate_repository_path(file_path)

    def test_rejects_directory_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_path = Path(temporary_directory)

            with self.assertRaisesRegex(ValueError, "目标不是 Git 仓库"):
                validate_repository_path(directory_path)


class ResolveRepositoryPathTests(unittest.TestCase):
    def test_accepts_path_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_path = Path(temporary_directory) / "repository"
            repository_path.mkdir()
            (repository_path / ".git").mkdir()
            file_path = repository_path / "docs" / "README.md"
            file_path.parent.mkdir()
            file_path.write_text("example", encoding="utf-8")

            result = resolve_repository_path(repository_path, "docs/README.md")

            self.assertEqual(result, file_path.resolve())

    def test_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_path = Path(temporary_directory) / "repository"
            repository_path.mkdir()
            (repository_path / ".git").mkdir()
            outside_path = Path(temporary_directory) / "outside.txt"

            with self.assertRaisesRegex(ValueError, "只允许仓库内的相对路径"):
                resolve_repository_path(repository_path, outside_path.resolve())

    def test_rejects_parent_directory_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_path = Path(temporary_directory) / "repository"
            repository_path.mkdir()
            (repository_path / ".git").mkdir()

            with self.assertRaisesRegex(ValueError, "禁止访问仓库外路径"):
                resolve_repository_path(repository_path, "../outside.txt")

    def test_rejects_symbolic_link_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_path = Path(temporary_directory) / "repository"
            repository_path.mkdir()
            (repository_path / ".git").mkdir()
            outside_path = Path(temporary_directory) / "outside.txt"
            outside_path.write_text("outside", encoding="utf-8")
            link_path = repository_path / "outside-link.txt"

            try:
                link_path.symlink_to(outside_path)
            except OSError as error:
                self.skipTest(f"当前系统不允许创建符号链接：{error}")

            with self.assertRaisesRegex(ValueError, "禁止访问仓库外路径"):
                resolve_repository_path(repository_path, "outside-link.txt")


class ValidateSafeFilePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_path = Path(self.temporary_directory.name)
        (self.repository_path / ".git").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_accepts_normal_text_file(self) -> None:
        file_path = self.repository_path / "README.md"
        file_path.write_text("example", encoding="utf-8")

        result = validate_safe_file_path(self.repository_path, "README.md")

        self.assertEqual(result, file_path.resolve())

    def test_allows_environment_example_template(self) -> None:
        file_path = self.repository_path / ".env.example"
        file_path.write_text("TOKEN=example", encoding="utf-8")

        result = validate_safe_file_path(self.repository_path, ".env.example")

        self.assertEqual(result, file_path.resolve())

    def test_rejects_git_internal_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止访问敏感目录"):
            validate_safe_file_path(self.repository_path, ".git/config")

    def test_rejects_environment_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止读取敏感文件"):
            validate_safe_file_path(self.repository_path, ".env")

    def test_rejects_named_environment_variant(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止读取敏感文件"):
            validate_safe_file_path(self.repository_path, ".env.local")

    def test_rejects_private_key_suffix(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止读取敏感文件"):
            validate_safe_file_path(self.repository_path, "deploy.pem")


class ReadProjectFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_path = Path(self.temporary_directory.name)
        (self.repository_path / ".git").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_reads_utf8_text_file(self) -> None:
        file_path = self.repository_path / "README.md"
        file_path.write_text("你好，仓库！", encoding="utf-8")

        result = read_project_file(self.repository_path, "README.md")

        self.assertEqual(result, "你好，仓库！")

    def test_truncates_long_text(self) -> None:
        file_path = self.repository_path / "long.txt"
        file_path.write_text("a" * 200, encoding="utf-8")

        result = read_project_file(self.repository_path, "long.txt", max_chars=80)

        self.assertEqual(len(result), 80)
        self.assertTrue(result.endswith("[内容已截断]"))

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "文件不存在"):
            read_project_file(self.repository_path, "missing.md")

    def test_rejects_directory(self) -> None:
        directory_path = self.repository_path / "docs"
        directory_path.mkdir()

        with self.assertRaisesRegex(ValueError, "目标不是普通文件"):
            read_project_file(self.repository_path, "docs")

    def test_rejects_disallowed_file_type(self) -> None:
        file_path = self.repository_path / "image.png"
        file_path.write_bytes(b"not-an-image")

        with self.assertRaisesRegex(ValueError, "不允许读取该文件类型"):
            read_project_file(self.repository_path, "image.png")

    def test_rejects_binary_content_with_text_suffix(self) -> None:
        file_path = self.repository_path / "binary.txt"
        file_path.write_bytes(b"hello\x00world")

        with self.assertRaisesRegex(ValueError, "检测到二进制文件"):
            read_project_file(self.repository_path, "binary.txt")

    def test_rejects_oversized_file(self) -> None:
        file_path = self.repository_path / "large.txt"
        file_path.write_bytes(b"a" * 101)

        with self.assertRaisesRegex(ValueError, "文件过大"):
            read_project_file(self.repository_path, "large.txt", max_file_bytes=100)


class ListProjectFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_path = Path(self.temporary_directory.name)
        (self.repository_path / ".git").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_safe_text_files_in_sorted_order(self) -> None:
        (self.repository_path / "src").mkdir()
        (self.repository_path / "README.md").write_text("readme", encoding="utf-8")
        (self.repository_path / "src" / "app.py").write_text("print('hi')", encoding="utf-8")

        result = list_project_files(self.repository_path)

        self.assertEqual(result.splitlines(), ["README.md", "src/app.py"])

    def test_skips_sensitive_and_non_text_files(self) -> None:
        (self.repository_path / ".env").write_text("SECRET=value", encoding="utf-8")
        (self.repository_path / ".env.example").write_text("SECRET=example", encoding="utf-8")
        (self.repository_path / ".gitignore").write_text(".env", encoding="utf-8")
        (self.repository_path / "image.png").write_bytes(b"image")
        (self.repository_path / ".git" / "config").write_text("git", encoding="utf-8")
        (self.repository_path / "notes.txt").write_text("notes", encoding="utf-8")

        result = list_project_files(self.repository_path)

        self.assertEqual(result.splitlines(), [".env.example", ".gitignore", "notes.txt"])

    def test_respects_directory_depth_limit(self) -> None:
        level_one = self.repository_path / "level-one"
        level_two = level_one / "level-two"
        level_two.mkdir(parents=True)
        (level_one / "visible.md").write_text("visible", encoding="utf-8")
        (level_two / "hidden.md").write_text("hidden", encoding="utf-8")

        result = list_project_files(self.repository_path, max_depth=1)

        self.assertEqual(result, "level-one/visible.md")

    def test_respects_file_count_limit(self) -> None:
        for index in range(3):
            (self.repository_path / f"file-{index}.txt").write_text("text", encoding="utf-8")

        result = list_project_files(self.repository_path, max_files=2)

        self.assertEqual(
            result.splitlines(),
            ["file-0.txt", "file-1.txt", "[文件列表已截断，最多显示 2 个文件]"],
        )


if __name__ == "__main__":
    unittest.main()
