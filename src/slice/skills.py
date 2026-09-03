"""Skill loader and parser for Slice IDE."""

import os
from pathlib import Path
from typing import Dict, List, Optional
import re


class Skill:
    """Represents a single skill with its metadata and instructions."""

    def __init__(self, name: str, description: str, instructions: str, metadata: Dict = None):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.metadata = metadata or {}

    def __repr__(self):
        return f"Skill(name='{self.name}', description='{self.description}')"


class SkillLoader:
    """Loads and manages skills from the skills/ directory."""

    SKILLS_DIR = "skills"

    def __init__(self, working_directory: str):
        self.working_directory = working_directory
        self.skills: Dict[str, Skill] = {}

    SKILL_FILENAME = "skill.md"

    def load_skills(self) -> Dict[str, Skill]:
        """
        Load all skills from the skills/ directory.
        Each skill is a subdirectory containing a skill.md file.
        The subdirectory name is used as the skill invocation name.
        Returns a dict mapping skill names to Skill objects.
        """
        skills_path = Path(self.working_directory) / self.SKILLS_DIR

        if not skills_path.exists() or not skills_path.is_dir():
            return {}

        for entry in sorted(skills_path.iterdir()):
            if not entry.is_dir():
                continue

            skill_file = entry / self.SKILL_FILENAME
            if not skill_file.exists():
                continue

            skill_name = entry.name
            try:
                skill = self._parse_skill_file(skill_file, skill_name)
                if skill:
                    self.skills[skill.name] = skill
            except Exception as e:
                print(f"Warning: Failed to load skill from {entry.name}/: {e}")

        return self.skills

    def _parse_skill_file(self, file_path: Path, skill_name: str) -> Optional[Skill]:
        """
        Parse a skill.md file with frontmatter.

        The skill invocation name comes from the parent directory name.
        Frontmatter 'description' is required. 'name' in frontmatter is
        ignored — the folder name is always the canonical name.

        Expected layout:
        skills/
          my-skill/
            skill.md

        Expected skill.md format:
        ---
        description: Brief description
        ---

        Instructions go here...
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            raise ValueError(f"Could not read file: {e}")

        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)

        if not frontmatter_match:
            raise ValueError("skill.md does not contain valid frontmatter (---...---)")

        frontmatter_text = frontmatter_match.group(1)
        instructions = frontmatter_match.group(2).strip()

        metadata = {}
        description = None

        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key == 'description':
                description = value
            elif key != 'name':
                metadata[key] = value

        if not description:
            raise ValueError(f"skill.md missing required 'description' field in frontmatter")
        if not instructions:
            raise ValueError(f"skill.md has no instructions after frontmatter")

        return Skill(name=skill_name, description=description, instructions=instructions, metadata=metadata)

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def has_skills(self) -> bool:
        """Check if any skills are loaded."""
        return len(self.skills) > 0

    def list_skill_names(self) -> List[str]:
        """Get a list of all loaded skill names."""
        return list(self.skills.keys())
