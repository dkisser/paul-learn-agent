import re
from pathlib import Path
from typing import Dict, List

from agent.tools.tool_manager import ToolsProvider, registry


class SkillsStore:
    """技能存储类"""

    _DEFAULT_SKILL_CATEGORY = "default"

    def __init__(self, workspace_path: str = "./"):
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.skills_dir = self.workspace_path / "skills"
        self.skills: Dict[str, List[Dict[str, str]]] = {}
        self._scan_skills()

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """解析 markdown 文件的 frontmatter，返回 (metadata, body_content)"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        frontmatter_text = match.group(1)
        body = match.group(2)

        metadata = {}
        for line in frontmatter_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                # 处理数组格式: ["a", "b"] 或 [a, b]
                if value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1].strip()
                    if inner:
                        items = []
                        for item in inner.split(","):
                            item = item.strip().strip('"').strip("'")
                            if item:
                                items.append(item)
                        value = items
                    else:
                        value = []
                metadata[key] = value

        return metadata, body

    def _scan_skills(self):
        """扫描 skills 目录，加载所有技能列表"""
        skills_list = []

        if self.skills_dir.exists() and self.skills_dir.is_dir():
            for skill_dir in sorted(self.skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"

                if not skill_md.exists():
                    continue
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    metadata, _ = self._parse_frontmatter(content)
                    name = metadata.get("name")
                    if not name:
                        continue
                    skills_list.append(
                        {
                            "name": name,
                            "description": metadata.get("description", ""),
                        }
                    )
                except Exception:
                    continue

        self.skills[self._DEFAULT_SKILL_CATEGORY] = skills_list

    def _find_skill_dir(self, name: str) -> Path | None:
        """根据技能名称查找技能目录"""
        if not self.skills_dir.exists():
            return None

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                metadata, _ = self._parse_frontmatter(content)
                if metadata.get("name") == name:
                    return skill_dir
            except Exception:
                continue
        return None

    def skill_view(self, name: str, file_path: str = None) -> dict:
        skill_dir = self._find_skill_dir(name)
        if not skill_dir:
            return {"success": False, "error": f"Skill '{name}' not found"}

        skill_md = skill_dir / "SKILL.md"

        if file_path:
            # 返回关联文件内容
            target_file = skill_dir / file_path
            if not target_file.exists() or not target_file.is_file():
                return {
                    "success": False,
                    "error": f"File '{file_path}' not found in skill '{name}'",
                }

            # 尝试作为文本文件读取
            try:
                content = target_file.read_text(encoding="utf-8")
                return {
                    "success": True,
                    "name": name,
                    "file": file_path,
                    "content": content,
                    "file_type": target_file.suffix,
                }
            except (UnicodeDecodeError, Exception):
                # 二进制文件
                file_size = target_file.stat().st_size
                return {
                    "success": True,
                    "name": name,
                    "file": file_path,
                    "content": f"[Binary file: {target_file.name}, size: {file_size} bytes]",
                    "is_binary": True,
                }

        # 不传 file_path，返回 SKILL.md 的完整信息
        try:
            content = skill_md.read_text(encoding="utf-8")
            metadata, body = self._parse_frontmatter(content)
        except Exception as e:
            return {"success": False, "error": f"Error reading SKILL.md: {e}"}

        # 收集关联文件列表
        linked_files: dict[str, list[str]] = {
            "references": [],
            "templates": [],
            "assets": [],
            "scripts": [],
        }

        for subdir_name in ["references", "templates", "assets", "scripts"]:
            subdir = skill_dir / subdir_name
            if subdir.exists() and subdir.is_dir():
                for file in sorted(subdir.iterdir()):
                    if file.is_file():
                        linked_files[subdir_name].append(f"{subdir_name}/{file.name}")

        return {
            "success": True,
            "name": metadata.get("name", name),
            "description": metadata.get("description", ""),
            "related_skills": metadata.get("related_skills", []),
            "content": body.strip(),
            "path": str(skill_md.relative_to(self.workspace_path)),
            "usage_hint": "To view linked files, call skill_view(name, file_path) where file_path is e.g. 'references/api.md' or 'assets/config.yaml'",
            "linked_files": linked_files,
        }

    def skill_list(self, category: str = None) -> List[Dict[str, str]]:
        if not category:
            return self.skills.get(self._DEFAULT_SKILL_CATEGORY, [])
        return self.skills.get(category, [])


class SkillViewTool(ToolsProvider):
    """技能工具"""

    SKILL_VIEW_SCHEMA = {
        "name": "skill_view",
        "description": "Skills allow for loading information about specific tasks and workflows, as well as scripts and templates. Load a skill's full content or access its linked files (references, templates, scripts). First call returns SKILL.md content plus a 'linked_files' dict showing available references/templates/scripts. To access those, call again with file_path parameter.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill name (use skills_list to see available skills)",
                },
                "file_path": {
                    "type": "string",
                    "description": "OPTIONAL: Path to a linked file within the skill (e.g., 'references/api.md', 'templates/config.yaml', 'scripts/validate.py'). Omit to get the main SKILL.md content.",
                },
            },
            "required": ["name"],
        },
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.SKILL_VIEW_SCHEMA

    def do_invoke(self, tool_input: dict, **kwargs) -> str:
        import json

        skill_store = kwargs.get("skill_store")
        if not skill_store:
            raise ValueError("skill_store is required")
        result = skill_store.skill_view(**tool_input)
        return json.dumps(result, ensure_ascii=False)


class SkillListTool(ToolsProvider):
    """技能列表工具"""

    SKILLS_LIST_SCHEMA = {
        "name": "skills_list",
        "description": "List available skills (name + description). Use skill_view(name) to load full content.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter to narrow results",
                }
            },
            "required": [],
        },
    }

    def get_schema(self, llm_provider: str) -> dict:
        return self.SKILLS_LIST_SCHEMA

    def do_invoke(self, tool_input: dict, **kwargs) -> str:
        import json

        skill_store = kwargs.get("skill_store")
        if not skill_store:
            raise ValueError("skill_store is required")
        result = skill_store.skill_list(**tool_input)
        return json.dumps(result, ensure_ascii=False)


registry.register("skill_view", SkillViewTool)
registry.register("skills_list", SkillListTool)
