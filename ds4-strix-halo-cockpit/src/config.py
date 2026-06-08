import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
MODELS_JSON = ASSETS_DIR / "models.json"
TOOLBOXES_JSON = ASSETS_DIR / "toolboxes.json"

def load_models() -> dict:
    if MODELS_JSON.exists():
        with open(MODELS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"repo": "antirez/deepseek-v4-gguf", "models": []}

def load_toolboxes() -> dict:
    if TOOLBOXES_JSON.exists():
        with open(TOOLBOXES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_registry() -> str:
    """Returns the Docker registry from toolboxes.json."""
    data = load_toolboxes()
    return data.get("registry", "")
