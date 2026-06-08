import os
import json
import sys
from pathlib import Path

CONFIG_FILE = Path(os.path.expanduser("~/.ds4-cockpit.conf"))

def get_models_dir() -> Path:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                conf = json.load(f)
                if "models_dir" in conf:
                    return Path(os.path.expanduser(conf["models_dir"]))
        except Exception:
            pass
    return Path(os.path.expanduser("~/ds4"))

def save_models_dir(path_str: str) -> bool:
    conf = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                conf = json.load(f)
        except Exception:
            pass
    
    conf["models_dir"] = path_str
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(conf, f, indent=4)
        
        new_dir = Path(os.path.expanduser(path_str))
        new_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def scan_local_models() -> list[dict]:
    models_dir = get_models_dir()
    if not models_dir.exists():
        return []
    
    found = []
    for f in os.listdir(models_dir):
        if f.endswith(".gguf"):
            found.append({
                "name": f,
                "path": str(models_dir / f)
            })
                    
    return sorted(found, key=lambda x: x["name"])

def is_model_downloaded(filename: str) -> bool:
    models_dir = get_models_dir()
    if not models_dir.exists():
        return False
        
    return (models_dir / filename).exists()

def get_download_cmd(repo: str, filename: str) -> list[str]:
    final_dir = str(get_models_dir())
    
    # Use the hf executable from the current Python environment
    hf_bin = os.path.join(os.path.dirname(sys.executable), "hf")
    if not os.path.exists(hf_bin):
        hf_bin = "hf" # Fallback to PATH if not found
    
    cmd = [
        hf_bin, "download",
        repo,
        filename,
        "--local-dir", final_dir
    ]
    return cmd
