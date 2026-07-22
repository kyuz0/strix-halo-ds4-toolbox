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

def get_model_server_defaults(model_path: str) -> dict:
    """Return curated server defaults for a local model, matched by filename or family."""
    filename = Path(model_path).name
    data = load_models()
    families = data.get("families", {})
    
    res = dict(data.get("default_server_defaults", {}))
    
    for model in data.get("models", []):
        if model.get("filename") == filename:
            family_name = model.get("family")
            if family_name and family_name in families:
                res.update(families[family_name])
            res.update(model.get("server_defaults", {}))
            return res

    # Heuristic fallback for unlisted local model filenames
    if "GLM" in filename.upper():
        if "glm-5.2" in families:
            res.update(families["glm-5.2"])
        else:
            res.update({"ssd_streaming": True, "coordinator_layers": "0:37", "worker_layers": "38:output"})
    else:
        if "deepseek-v4" in families:
            res.update(families["deepseek-v4"])
        else:
            res.update({"coordinator_layers": "0:21", "worker_layers": "22:output"})

    return res

def load_toolboxes() -> dict:
    if TOOLBOXES_JSON.exists():
        with open(TOOLBOXES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_registry() -> str:
    """Returns the Docker registry from toolboxes.json."""
    data = load_toolboxes()
    return data.get("registry", "")
