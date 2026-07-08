import subprocess
import os
import urllib.request
import json
import shutil
import re
from datetime import datetime, timezone
from .config import load_toolboxes

def upgrade_groups_for_podman(engine: str, args: list[str]) -> list[str]:
    """When using podman, replace --group-add video/render with --group-add keep-groups.
    
    Podman's --group-add with named groups resolves GIDs inside the container,
    which may not match the host's video/render GIDs needed for /dev/kfd access.
    --group-add keep-groups passes through all host supplementary GIDs by number.
    Docker does not support keep-groups, so we leave args unchanged for Docker.
    """
    if engine != "podman":
        return list(args)
    result = []
    added_keep = False
    i = 0
    while i < len(args):
        if args[i] == "--group-add" and i + 1 < len(args) and args[i+1] in ("video", "render"):
            if not added_keep:
                result.extend(["--group-add", "keep-groups"])
                added_keep = True
            i += 2
        else:
            result.append(args[i])
            i += 1
    return result

def parse_date_to_ts(date_str: str) -> float:
    if not date_str:
        return 0.0
    try:
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+([+-]\d{4})', date_str)
        if m:
            iso_str = f"{m.group(1)}T{m.group(2)}{m.group(3)}"
            return datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).timestamp()
        
        if 'T' in date_str:
            ds = date_str.replace('Z', '+00:00')
            return datetime.fromisoformat(ds).astimezone(timezone.utc).timestamp()
    except Exception:
        pass
    return 0.0

def detect_engines() -> list[str]:
    engines = []
    if shutil.which("podman"):
        engines.append("podman")
    if shutil.which("docker"):
        engines.append("docker")
    return engines

def get_toolbox_engine() -> str:
    is_debian_arch = False
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            content = f.read().lower()
            if any(x in content for x in ["id=ubuntu", "id=debian", "id=arch", "id_like=ubuntu", "id_like=debian", "id_like=arch"]):
                is_debian_arch = True

    if is_debian_arch:
        engines = detect_engines()
        return "podman" if "podman" in engines else "docker"
    return "podman"

def get_os_toolbox_cmd() -> str:
    prefer_distrobox = False
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            content = f.read().lower()
            if any(x in content for x in ["id=ubuntu", "id=debian", "id=arch", "id_like=ubuntu", "id_like=debian", "id_like=arch"]):
                prefer_distrobox = True

    if prefer_distrobox and shutil.which("distrobox"):
        return "distrobox"
    elif shutil.which("toolbox"):
        return "toolbox"
    elif shutil.which("distrobox"):
        return "distrobox"

    return "distrobox" if prefer_distrobox else "toolbox"

def get_installed_toolboxes(registry_match: str, specific_engine: str = None) -> list[dict]:
    """Returns a list of dicts with name, image, status, engine."""
    engines = [specific_engine] if specific_engine else detect_engines()
    toolboxes = []
    
    for engine in engines:
        try:
            res = subprocess.run(
                [engine, "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}|{{.CreatedAt}}"], 
                capture_output=True, text=True, check=True
            )
            lines = res.stdout.strip().split('\n')
            for line in lines:
                if not line: continue
                parts = line.split('|')
                if len(parts) >= 3:
                    name, image, status = parts[0], parts[1], parts[2]
                    name = name.strip()
                    image = image.strip()
                    status = status.strip()
                    status = status.replace("292 years ago", "Unknown Date")
                    
                    created = ""
                    created_ts = 0.0
                    if len(parts) >= 4:
                        created_raw = parts[3].strip()
                        created = created_raw.split()[0] if created_raw else ""
                        created_ts = parse_date_to_ts(created_raw)
                    
                    # Normalize by stripping docker.io/ prefix for robust matching
                    r_norm = registry_match.replace("docker.io/", "") if registry_match else ""
                    i_norm = image.replace("docker.io/", "")
                    if r_norm and r_norm in i_norm:
                        toolboxes.append({
                            "name": name,
                            "image": image,
                            "status": status,
                            "created": created,
                            "created_ts": created_ts,
                            "engine": engine
                        })
        except Exception:
            pass
    return toolboxes

def get_all_toolboxes() -> dict:
    config_data = load_toolboxes()
    registry_match = config_data.get("registry", "")
    engine = get_toolbox_engine()
    installed = get_installed_toolboxes(registry_match, engine)
    
    installed_dict = {tb["name"]: tb for tb in installed}
    
    grouped_toolboxes = {}
    
    for group in config_data.get("groups", []):
        group_name = group.get("name", "Unknown Group")
        grouped_toolboxes[group_name] = []
        
        for ctb in group.get("toolboxes", []):
            name = ctb["name"]
            tag = ctb.get("tag", "latest")
            desc = ctb.get("description", "")
            image = f"{registry_match}:{tag}"
            
            if name in installed_dict:
                tb = installed_dict[name]
                tb["args"] = ctb.get("engine_args", [])
                tb["description"] = desc
                tb["group"] = group_name
                tb["server_binary"] = ctb.get("server_binary", "ds4-server")
                grouped_toolboxes[group_name].append(tb)
                del installed_dict[name]
            else:
                grouped_toolboxes[group_name].append({
                    "name": name,
                    "image": image,
                    "description": desc,
                    "status": "Not Installed",
                    "created": "",
                    "created_ts": 0.0,
                    "engine": engine,
                    "args": ctb.get("engine_args", []),
                    "group": group_name,
                    "server_binary": ctb.get("server_binary", "ds4-server")
                })
                
    unsupported = []
    for tb in installed_dict.values():
        tb["args"] = []
        tb["description"] = ""
        tb["group"] = "Unsupported / Legacy"
        tb["server_binary"] = "ds4-server"
        if "created" not in tb:
            tb["created"] = ""
            tb["created_ts"] = 0.0
        unsupported.append(tb)
        
    if unsupported:
        grouped_toolboxes["Unsupported / Legacy"] = unsupported
        
    return grouped_toolboxes

def create_toolbox(name: str, image: str, args: list[str]):
    cmd = get_os_toolbox_cmd()
    engine = get_toolbox_engine()
    os.environ["DBX_CONTAINER_MANAGER"] = engine
    
    # Pull first
    subprocess.run([engine, "pull", image], check=True)
    
    resolved_args = upgrade_groups_for_podman(engine, args)
    full_cmd = [cmd, "create", name, "--image", image]
    if resolved_args:
        full_cmd.append("--")
        full_cmd.extend(resolved_args)
    subprocess.run(full_cmd, check=True)

def delete_toolbox(name: str):
    cmd = get_os_toolbox_cmd()
    os.environ["DBX_CONTAINER_MANAGER"] = get_toolbox_engine()
    subprocess.run([cmd, "rm", "-f", name], check=True)

def get_remote_image_date(image: str) -> str:
    if not ("docker.io" in image or "kyuz0" in image):
        return None
    parts = image.split(':')
    repo = parts[0].replace('docker.io/', '')
    tag = parts[1] if len(parts) > 1 else "latest"
    
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("last_updated")
    except Exception:
        return None
