from agent.tools.tool_manager import ToolsProvider, registry


class ReadFileTool(ToolsProvider):
    """读取文件工具"""

    READ_FILE_SCHEMA = {
        "name": "read_file",
        "description": "Read a text file with line numbers and pagination. Use this instead of cat/head/tail in terminal. Output format: 'LINE_NUM|CONTENT'. Suggests similar filenames if not found. Use offset and limit for large files. Reads exceeding ~100K characters are rejected; use offset and limit to read specific sections of large files. NOTE: Cannot read images or binary files — use vision_analyze for images.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read (absolute, relative, or ~/path)"},
                "offset": {"type": "integer",
                           "description": "Line number to start reading from (1-indexed, default: 1)", "default": 1,
                           "minimum": 1},
                "limit": {"type": "integer", "description": "Maximum number of lines to read (default: 500, max: 2000)",
                          "default": 500, "maximum": 2000}
            },
            "required": ["path"]
        }
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.READ_FILE_SCHEMA

    def do_invoke(self, tool_input: dict) -> str:
        from pathlib import Path
        path = Path(tool_input['path']).expanduser()
        if not path.exists():
            return f"Error: File not found: {path}"
        if not path.is_file():
            return f"Error: Not a file: {path}"
        offset = tool_input.get('offset', 1)
        limit = tool_input.get('limit', 500)
        try:
            content = path.read_text(encoding='utf-8')
        except Exception as e:
            return f"Error reading file: {e}"
        lines = content.splitlines()
        # offset 是 1-indexed
        start = max(0, offset - 1)
        end = min(start + limit, len(lines))
        selected = lines[start:end]
        result_lines = []
        for idx, line in enumerate(selected):
            result_lines.append(f'{start + 1 + idx}|{line}')
        output = '\n'.join(result_lines)
        total = len(lines)
        if end < total:
            output += f'\n... ({total - end} more lines, use offset={end + 1} to continue)'
        return output


class SearchFileTool(ToolsProvider):
    """搜索文件工具"""

    SEARCH_FILES_SCHEMA = {
        "name": "search_files",
        "description": "Search file contents or find files by name. Use this instead of grep/rg/find/ls in terminal. Ripgrep-backed, faster than shell equivalents.\n\nContent search (target='content'): Regex search inside files. Output modes: full matches with line numbers, file paths only, or match counts.\n\nFile search (target='files'): Find files by glob pattern (e.g., '*.py', '*config*'). Also use this instead of ls — results sorted by modification time.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string",
                            "description": "Regex pattern for content search, or glob pattern (e.g., '*.py') for file search"},
                "target": {"type": "string", "enum": ["content", "files"],
                           "description": "'content' searches inside file contents, 'files' searches for files by name",
                           "default": "content"},
                "path": {"type": "string",
                         "description": "Directory or file to search in (default: current working directory)",
                         "default": "."},
                "file_glob": {"type": "string",
                              "description": "Filter files by pattern in grep mode (e.g., '*.py' to only search Python files)"},
                "limit": {"type": "integer", "description": "Maximum number of results to return (default: 50)",
                          "default": 50},
                "offset": {"type": "integer", "description": "Skip first N results for pagination (default: 0)",
                           "default": 0},
                "output_mode": {"type": "string", "enum": ["content", "files_only", "count"],
                                "description": "Output format for grep mode: 'content' shows matching lines with line numbers, 'files_only' lists file paths, 'count' shows match counts per file",
                                "default": "content"},
                "context": {"type": "integer",
                            "description": "Number of context lines before and after each match (grep mode only)",
                            "default": 0}
            },
            "required": ["pattern"]
        }
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.SEARCH_FILES_SCHEMA


    def do_invoke(self, tool_input: dict) -> str:
        import subprocess
        import shutil
        from pathlib import Path

        pattern = tool_input['pattern']
        target = tool_input.get('target', 'content')
        search_path = Path(tool_input.get('path', '.')).expanduser()
        file_glob: str | None = tool_input.get('file_glob')
        limit = tool_input.get('limit', 50)
        offset = tool_input.get('offset', 0)
        output_mode = tool_input.get('output_mode', 'content')
        context = tool_input.get('context', 0)

        if target == 'files':
            # File search by glob pattern
            try:
                matched = sorted(search_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            except Exception as e:
                return f"Error searching files: {e}"
            total = len(matched)
            sliced = matched[offset:offset + limit]
            if output_mode == 'count':
                return f'Found {total} files, showing {len(sliced)}'
            lines = [f'{p}' for p in sliced]
            return '\n'.join(lines) if lines else 'No files found'
        else:
            # Content search: ripgrep first, fallback to grep
            if not search_path.exists():
                return f"Error: Path not found: {search_path}"

            use_rg = shutil.which('rg') is not None

            cmd: list[str]
            if use_rg:
                cmd = ['rg', '--no-heading', '--line-number', '--color=never']
                if output_mode == 'files_only':
                    cmd.append('--files-with-matches')
                elif output_mode == 'count':
                    cmd.append('--count')
                if context > 0:
                    cmd.extend(['--context', str(context)])
                if file_glob:
                    cmd.extend(['--glob', file_glob])
            else:
                if output_mode == 'files_only':
                    cmd = ['grep', '-rl', '--color=never']
                elif output_mode == 'count':
                    cmd = ['grep', '-rc', '--color=never']
                else:
                    cmd = ['grep', '-rn', '--color=never']
                if context > 0:
                    cmd.extend(['-C', str(context)])
                if file_glob:
                    cmd.extend(['--include', file_glob])
            cmd.extend([pattern, str(search_path)])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except FileNotFoundError:
                return "Error: neither ripgrep (rg) nor grep found."
            except subprocess.TimeoutExpired:
                return "Error: search timed out"
            if result.returncode == 1:
                return 'No matches found'
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            lines = result.stdout.strip().splitlines()
            total = len(lines)
            sliced = lines[offset:offset + limit]
            return '\n'.join(sliced) if sliced else 'No matches found'


class WriteFileTool(ToolsProvider):
    """写入文件工具"""

    WRITE_FILE_SCHEMA = {
        "name": "write_file",
        "description": "Write content to a file, completely replacing existing content. Use this instead of echo/cat heredoc in terminal. Creates parent directories automatically. OVERWRITES the entire file — use 'patch' for targeted edits.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Path to the file to write (will be created if it doesn't exist, overwritten if it does)"},
                "content": {"type": "string", "description": "Complete content to write to the file"}
            },
            "required": ["path", "content"]
        }
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.WRITE_FILE_SCHEMA

    def do_invoke(self, tool_input: dict) -> str:
        from pathlib import Path
        import shutil

        path = Path(tool_input['path']).expanduser()
        content = tool_input['content']

        try:
            # 如果文件已存在，先备份
            if path.exists():
                backup = path.with_suffix(path.suffix + '.bak')
                shutil.copy2(path, backup)
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return f'Successfully wrote {len(content)} bytes to {path}'
        except Exception as e:
            return f'Error writing file: {e}'


registry.register("read_file", ReadFileTool)
registry.register("write_file", WriteFileTool)
registry.register("search_files", SearchFileTool)