
import pytest
import yaml

from app.services.prompt_manager import PromptManager


@pytest.fixture
def temp_prompts_dir(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create a mock prompt
    test_prompt = {
        "name": "test_prompt",
        "active_version": "v1",
        "versions": {
            "v1": {
                "template": "Hello {name} v1!"
            },
            "v2": {
                "template": "Greetings {name} v2!"
            }
        }
    }

    with open(prompts_dir / "test_prompt.yaml", "w") as f:
        yaml.dump(test_prompt, f)

    return prompts_dir

def test_prompt_manager_loads_active_version_by_default(temp_prompts_dir):
    manager = PromptManager(prompts_dir=temp_prompts_dir)
    template = manager.get_prompt("test_prompt")
    assert template == "Hello {name} v1!"

def test_prompt_manager_loads_specific_version(temp_prompts_dir):
    manager = PromptManager(prompts_dir=temp_prompts_dir)
    template = manager.get_prompt("test_prompt", version="v2")
    assert template == "Greetings {name} v2!"

def test_prompt_manager_raises_on_missing_file(temp_prompts_dir):
    manager = PromptManager(prompts_dir=temp_prompts_dir)
    with pytest.raises(FileNotFoundError):
        manager.get_prompt("nonexistent")

def test_prompt_manager_raises_on_missing_version(temp_prompts_dir):
    manager = PromptManager(prompts_dir=temp_prompts_dir)
    with pytest.raises(KeyError):
        manager.get_prompt("test_prompt", version="v3")
