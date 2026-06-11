import os
import shlex
from src.model_manager import get_models_dir

def build_server_cmd(engine: str, image: str, model_path: str, ctx: int, 
                     host: str, port: str, kv_disk_dir: str, kv_disk_mb: int,
                     mtp_path: str, custom_args: str,
                     role: str, layers: str, peer_addr: str,
                     toolbox_config: dict) -> list[str]:
    
    models_dir = str(get_models_dir())
    engine_args = toolbox_config.get("args", [])
    server_binary = toolbox_config.get("server_binary", "ds4-server")
    
    # Clean up toolbox engine_args (remove sudo)
    clean_args = []
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
        clean_args.append(engine_args[i])
    engine_args = clean_args

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
        
    port_mapping = f"{port}:{port}"
    if host and host != "0.0.0.0":
        bind_ip = "127.0.0.1" if host == "localhost" else host
        port_mapping = f"{bind_ip}:{port}:{port}"

    docker_args.extend([
        "-v", f"{models_dir}:/models:ro",
        "-p", port_mapping
    ])
    
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
        
    if role and role != "Standalone":
        server_args.extend(["--role", role.lower()])
        if layers:
            server_args.extend(["--layers", layers])
        if peer_addr:
            if ":" in peer_addr and len(peer_addr.split()) == 1:
                addr_parts = peer_addr.split(":")
            else:
                addr_parts = peer_addr.split()
                
            if len(addr_parts) == 1:
                addr_parts.append("8081")
                
            coord_ip = addr_parts[0]
            coord_port = addr_parts[1]
                
            if role.lower() == "coordinator":
                server_args.extend(["--listen", "0.0.0.0", coord_port])
                bind_ip = "0.0.0.0" if coord_ip == "0.0.0.0" else coord_ip
                docker_args.extend(["-p", f"{bind_ip}:{coord_port}:{coord_port}"])
            elif role.lower() == "worker":
                server_args.extend(["--coordinator", coord_ip, coord_port])

    if custom_args:
        server_args.extend(shlex.split(custom_args))
    
    return docker_args + [image] + server_args
