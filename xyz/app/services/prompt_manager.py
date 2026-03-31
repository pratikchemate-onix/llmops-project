import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

class PromptManager:
    """Manages versioned prompts loaded from YAML files."""

    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self.prompts_dir = prompts_dir

    def _load_prompt_file(self, prompt_name: str) -> dict:
        """Loads the YAML file for a given prompt name."""
        file_path = self.prompts_dir / f"{prompt_name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                return data or {}
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse prompt YAML {file_path}: {e}")
                raise ValueError(f"Invalid YAML in prompt file: {file_path}") from e

    def get_prompt(self, prompt_name: str, version: str | None = None) -> str:
        """
        Retrieves the prompt template string.
        If version is not provided, retrieves the 'active_version' specified in the file.
        """
        data = self._load_prompt_file(prompt_name)

        target_version = version or data.get("active_version")
        if not target_version:
            raise ValueError(f"No active_version specified in {prompt_name}.yaml and no version provided.")

        versions = data.get("versions", {})
        if target_version not in versions:
            raise KeyError(f"Version {target_version} not found in {prompt_name}.yaml")

        version_data = versions[target_version]
        template = version_data.get("template")

        if not template:
            raise ValueError(f"No 'template' found for version {target_version} in {prompt_name}.yaml")

        return template

# Global instance
prompt_manager = PromptManager()
