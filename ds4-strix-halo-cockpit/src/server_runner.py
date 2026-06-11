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

    cmd = [engine, "run", "--rm", "-it"]
    cmd.extend(engine_args)
    
    # ROCm requires host IPC sharing and ptrace capabilities to avoid HSA memory mapping errors
    cmd.extend([
        "--ipc=host",
        "--cap-add=SYS_PTRACE"
    ])
        
    if engine == "podman":
        cmd.extend([
            "--security-opt", "label=disable",
            "--userns=keep-id"
        ])
        
    port_mapping = f"{port}:{port}"
    if host and host != "0.0.0.0":
        bind_ip = "127.0.0.1" if host == "localhost" else host
        port_mapping = f"{bind_ip}:{port}:{port}"

    cmd.extend([
        "-v", f"{models_dir}:/models:ro",
        "-p", port_mapping,
        image
    ])
    
    # Calculate relative paths for /models
    rel_path = os.path.relpath(model_path, models_dir)
    inner_model_path = f"/models/{rel_path}"

    cmd.extend([
        server_binary,
        "-m", inner_model_path,
        "--ctx", str(ctx),
        "--host", "0.0.0.0",
        "--port", str(port)
    ])
    
    if kv_disk_dir:
        cmd.extend(["--kv-disk-dir", kv_disk_dir, "--kv-disk-space-mb", str(kv_disk_mb)])
        
    if mtp_path:
        mtp_rel = os.path.relpath(mtp_path, models_dir)
        cmd.extend(["--mtp", f"/models/{mtp_rel}"])
        
    if role and role != "Standalone":
        cmd.extend(["--role", role.lower()])
        if layers:
            cmd.extend(["--layers", layers])
        if peer_addr:
            addr_parts = peer_addr.split()
            if role.lower() == "coordinator":
                cmd.extend(["--listen"])
                cmd.extend(addr_parts)
            elif role.lower() == "worker":
                cmd.extend(["--coordinator"])
                cmd.extend(addr_parts)

    if custom_args:
        cmd.extend(shlex.split(custom_args))
    
    return cmd
