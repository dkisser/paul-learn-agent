import pytest

from agent.tools.file_tool import ReadFileTool, SearchFileTool, WriteFileTool


# ──────────────── ReadFileTool ────────────────

@pytest.fixture
def read_tool():
    return ReadFileTool()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.txt"
    lines = [f"line {i}" for i in range(1, 21)]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


class TestReadFileTool:
    def test_read_full_file(self, read_tool, sample_file):
        result = read_tool.invoke({"path": str(sample_file)})
        lines = result.splitlines()
        assert len(lines) == 20
        assert lines[0] == "1|line 1"
        assert lines[19] == "20|line 20"

    def test_read_with_offset_and_limit(self, read_tool, sample_file):
        result = read_tool.invoke({"path": str(sample_file), "offset": 5, "limit": 3})
        lines = result.splitlines()
        # 3 行内容 + 1 行分页提示
        assert len(lines) == 4
        assert lines[0] == "5|line 5"
        assert lines[2] == "7|line 7"

    def test_read_pagination_hint(self, read_tool, sample_file):
        result = read_tool.invoke({"path": str(sample_file), "offset": 1, "limit": 5})
        assert "... (15 more lines" in result
        assert "use offset=6" in result

    def test_read_file_not_found(self, read_tool):
        result = read_tool.invoke({"path": "/nonexistent/path/file.txt"})
        assert "Error: File not found" in result

    def test_read_path_is_directory(self, read_tool, tmp_path):
        result = read_tool.invoke({"path": str(tmp_path)})
        assert "Error: Not a file" in result

    def test_read_expanduser_tilde(self, read_tool):
        # expanduser 将 ~ 展开为真实 home 路径，验证不抛异常即可
        result = read_tool.invoke({"path": "~/.nonexistent_file_12345"})
        assert "Error: File not found" in result

    def test_read_file_with_special_chars(self, read_tool, tmp_path):
        f = tmp_path / "special.txt"
        f.write_text("中文内容\nemoji: ✓\ntab\there", encoding="utf-8")
        result = read_tool.invoke({"path": str(f)})
        assert "1|中文内容" in result
        assert "3|tab\there" in result


# ──────────────── WriteFileTool ────────────────

@pytest.fixture
def write_tool():
    return WriteFileTool()


class TestWriteFileTool:
    def test_write_new_file(self, write_tool, tmp_path):
        path = tmp_path / "new_dir" / "new_file.txt"
        content = "hello world"
        result = write_tool.invoke({"path": str(path), "content": content})
        assert "Successfully wrote" in result
        assert path.read_text(encoding="utf-8") == content

    def test_overwrite_existing_file_creates_backup(self, write_tool, tmp_path):
        path = tmp_path / "existing.txt"
        path.write_text("old content", encoding="utf-8")
        write_tool.invoke({"path": str(path), "content": "new content"})
        assert path.read_text(encoding="utf-8") == "new content"
        # with_suffix('.txt' + '.bak') → .txt.bak
        backup = tmp_path / "existing.txt.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "old content"

    def test_write_empty_content(self, write_tool, tmp_path):
        path = tmp_path / "empty.txt"
        result = write_tool.invoke({"path": str(path), "content": ""})
        assert "Successfully wrote" in result
        assert path.read_text(encoding="utf-8") == ""

    def test_write_multiline(self, write_tool, tmp_path):
        path = tmp_path / "multi.txt"
        content = "line1\nline2\nline3"
        write_tool.invoke({"path": str(path), "content": content})
        assert path.read_text(encoding="utf-8") == content


# ──────────────── SearchFileTool ────────────────

@pytest.fixture
def search_tool():
    return SearchFileTool()


@pytest.fixture
def search_dir(tmp_path):
    (tmp_path / "hello.py").write_text("def hello():\n    print('hello')\n", encoding="utf-8")
    (tmp_path / "world.py").write_text("def world():\n    print('world')\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("This is a note about hello and world.\n", encoding="utf-8")
    return tmp_path


class TestSearchFileTool:
    def test_search_files_by_glob(self, search_tool, search_dir):
        result = search_tool.invoke({"pattern": "*.py", "target": "files", "path": str(search_dir)})
        lines = result.splitlines()
        assert len(lines) == 2
        assert any("hello.py" in l for l in lines)
        assert any("world.py" in l for l in lines)

    def test_search_files_no_match(self, search_tool, search_dir):
        result = search_tool.invoke({"pattern": "*.xyz", "target": "files", "path": str(search_dir)})
        assert "No files found" in result

    def test_search_files_count_mode(self, search_tool, search_dir):
        result = search_tool.invoke({
            "pattern": "*.py", "target": "files", "path": str(search_dir), "output_mode": "count"
        })
        assert "Found 2 files" in result

    def test_search_files_with_limit(self, search_tool, search_dir):
        result = search_tool.invoke({"pattern": "*.py", "target": "files", "path": str(search_dir), "limit": 1})
        lines = result.splitlines()
        assert len(lines) == 1

    def test_search_content_no_match(self, search_tool, search_dir):
        result = search_tool.invoke({"pattern": "NOTFOUND", "path": str(search_dir)})
        assert "No matches found" in result

    def test_search_content_path_not_found(self, search_tool):
        result = search_tool.invoke({"pattern": "test", "path": "/nonexistent/dir"})
        assert "Error: Path not found" in result

    def test_search_content_with_file_glob_filter(self, search_tool, search_dir):
        result = search_tool.invoke({
            "pattern": "hello", "path": str(search_dir), "file_glob": "*.py"
        })
        # Should only match .py files
        assert "hello" in result
        assert "notes.txt" not in result
