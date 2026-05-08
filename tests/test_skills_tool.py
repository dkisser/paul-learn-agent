"""Tests for SkillsStore and skill tools."""

import json
from pathlib import Path

import pytest

from agent.tools.skills_tool import SkillsStore

TESTS_DIR = Path(__file__).resolve().parent


class TestSkillsStore:
    """Test suite for SkillsStore functionality."""

    @pytest.fixture
    def store(self):
        """Fixture providing a SkillsStore instance pointing to test skills."""
        return SkillsStore(workspace_path=str(TESTS_DIR))

    def test_skill_list_returns_skills(self, store):
        skills = store.skill_list()
        assert len(skills) == 1
        assert skills[0]["name"] == "test-skill"
        assert (
            skills[0]["description"]
            == "A skill for sort alphabetically.If you want to write a sort method, you shuold use this skill."
        )

    def test_skill_list_empty_category(self, store):
        skills = store.skill_list("nonexistent")
        assert skills == []

    def test_skill_view_without_file_path(self, store):
        result = store.skill_view("test-skill")

        assert result["success"] is True
        assert result["name"] == "test-skill"
        assert (
            result["description"]
            == "A test skill for verifying SkillsStore functionality"
        )
        assert result["related_skills"] == ["other-skill", "another-skill"]
        assert "# Test Skill" in result["content"]
        assert result["path"] == "skills/test-skill/SKILL.md"
        assert "usage_hint" in result

        linked = result["linked_files"]
        assert linked["references"] == ["references/api.md"]
        assert linked["scripts"] == ["scripts/helper.py"]
        assert linked["templates"] == ["templates/config.yaml"]
        assert linked["assets"] == ["assets/logo.png"]

    def test_skill_view_with_reference_file(self, store):
        result = store.skill_view("test-skill", file_path="references/api.md")

        assert result["success"] is True
        assert result["name"] == "test-skill"
        assert result["file"] == "references/api.md"
        assert "# API Reference" in result["content"]
        assert result["file_type"] == ".md"

    def test_skill_view_with_script_file(self, store):
        result = store.skill_view("test-skill", file_path="scripts/helper.py")

        assert result["success"] is True
        assert result["file_type"] == ".py"
        assert "def helper_function()" in result["content"]

    def test_skill_view_with_template_file(self, store):
        result = store.skill_view("test-skill", file_path="templates/config.yaml")

        assert result["success"] is True
        assert result["file_type"] == ".yaml"
        assert "database:" in result["content"]

    def test_skill_view_binary_file(self, store):
        result = store.skill_view("test-skill", file_path="assets/logo.png")

        assert result["success"] is True
        assert result["is_binary"] is True
        assert "Binary file" in result["content"]
        assert "logo.png" in result["content"]

    def test_skill_view_skill_not_found(self, store):
        result = store.skill_view("non-existent-skill")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_skill_view_file_not_found(self, store):
        result = store.skill_view("test-skill", file_path="non-existent.md")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestSkillTools:
    """Test suite for SkillViewTool and SkillListTool."""

    @pytest.fixture
    def store(self):
        return SkillsStore(workspace_path=str(TESTS_DIR))

    def test_skill_list_tool_returns_json(self, store):
        from agent.tools.skills_tool import SkillListTool

        tool = SkillListTool()
        result = tool.do_invoke({}, skill_store=store)
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["name"] == "test-skill"

    def test_skill_view_tool_returns_json(self, store):
        from agent.tools.skills_tool import SkillViewTool

        tool = SkillViewTool()
        result = tool.do_invoke({"name": "test-skill"}, skill_store=store)
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert parsed["name"] == "test-skill"

    def test_skill_view_tool_missing_store_raises(self):
        from agent.tools.skills_tool import SkillViewTool

        tool = SkillViewTool()
        with pytest.raises(ValueError, match="skill_store is required"):
            tool.do_invoke({"name": "test-skill"})


