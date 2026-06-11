import os
import shlex
from src.model_manager import get_models_dir

def _parse_peer_addr(peer_addr: str) -> tuple[str, str]:
    """Parse peer address input into (ip, port). Supports 'IP PORT', 'IP:PORT', or bare 'IP'."""
    if ":" in peer_addr and len(peer_addr.split()) == 1:
        parts = peer_addr.split(":")
    else:
        parts = peer_addr.split()
    ip = parts[0]
    port = parts[1] if len(parts) > 1 else "8081"
    return ip, port

def _clean_engine_args(engine_args: list[str]) -> list[str]:
    """Remove --group-add sudo from engine args (not needed for server mode)."""
    clean = []
    skip_next = False
    for i in range(len(engine_args)):
        if skip_next:
            skip_next = False
            continue
        if engine_args[i] == "--group-add" and i + 1 < len(engine_args) and engine_args[i+1] == "sudo":
            skip_next = True
            continue
        if engine_args[i] == "--group-add=sudo":
            continue
        clean.append(engine_args[i])
    return clean

def build_server_cmd(engine: str, image: str, model_path: str, ctx: int, 
                     host: str, port: str, kv_disk_dir: str, kv_disk_mb: int,
                     mtp_path: str, custom_args: str,
                     role: str, layers: str, peer_addr: str,
                     toolbox_config: dict) -> list[str]:
    
    models_dir = str(get_models_dir())
    engine_args = _clean_engine_args(toolbox_config.get("args", []))
    server_binary = toolbox_config.get("server_binary", "ds4-server")
    
    is_multinode = role and role != "Standalone"

    docker_args = [engine, "run", "--rm", "-it"]
    docker_args.extend(engine_args)
    
    # ROCm requires host IPC sharing and ptrace capabilities to avoid HSA memory mapping errors
    docker_args.extend([
        "--ipc=host",
        "--cap-add=SYS_PTRACE"
    ])
        
    if engine == "podman":
        docker_args.extend([
            "--security-opt", "label=disable",
            "--userns=keep-id"
        ])

    if is_multinode:
        # Multi-node mode: use host networking so ds4-server can bind directly
        # to host IPs for --listen/--coordinator. Podman's rootless pasta
        # network backend cannot forward arbitrary host IPs via -p.
        docker_args.append("--network=host")
    else:
        # Standalone mode: use standard port mapping
        port_mapping = f"{port}:{port}"
        if host and host != "0.0.0.0":
            bind_ip = "127.0.0.1" if host == "localhost" else host
            port_mapping = f"{bind_ip}:{port}:{port}"
        docker_args.extend(["-p", port_mapping])

    docker_args.extend(["-v", f"{models_dir}:/models:ro"])
    
    # Calculate relative paths for /models
    rel_path = os.path.relpath(model_path, models_dir)
    inner_model_path = f"/models/{rel_path}"

    server_args = [
        server_binary,
        "-m", inner_model_path,
        "--ctx", str(ctx),
        "--host", "0.0.0.0",
        "--port", str(port)
    ]
    
    if kv_disk_dir:
        server_args.extend(["--kv-disk-dir", kv_disk_dir, "--kv-disk-space-mb", str(kv_disk_mb)])
        
    if mtp_path:
        mtp_rel = os.path.relpath(mtp_path, models_dir)
        server_args.extend(["--mtp", f"/models/{mtp_rel}"])
        
    if is_multinode:
        server_args.extend(["--role", role.lower()])
        if layers:
            server_args.extend(["--layers", layers])
        if peer_addr:
            coord_ip, coord_port = _parse_peer_addr(peer_addr)
            if role.lower() == "coordinator":
                server_args.extend(["--listen", coord_ip, coord_port])
            elif role.lower() == "worker":
                server_args.extend(["--coordinator", coord_ip, coord_port])

    if custom_args:
        server_args.extend(shlex.split(custom_args))
    
    return docker_args + [image] + server_args
