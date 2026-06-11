# AMD Strix Halo ds4 Toolbox

A pre-built container image ("toolbox") for running **[ds4](https://github.com/antirez/ds4)** — antirez's DeepSeek V4 Flash inference engine — on **AMD Ryzen AI Max "Strix Halo"** integrated GPUs (`gfx1151`).

This container is based on the `main` branch of `antirez/ds4` compiled against **ROCm 7.2.4 (stable)**. It exposes three compiled binaries: `ds4`, `ds4-server`, and `ds4-bench`.

* **Docker Hub Image:** [kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags)
* **Target Container System:** Toolbx (standard developer container system on Fedora) or Distrobox (works on Ubuntu, Debian, Arch, openSUSE, etc.)

---

## Host Configuration

Strix Halo uses unified memory. Add these kernel boot parameters to allocate up to 124 GiB for the iGPU:

```
amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856 ttm.page_pool_size=32505856
```

Apply with:
```bash
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo reboot
```

---

## Quick Start

### 1. Create and Enter the Toolbox

**Ubuntu/Debian:** replace `toolbox` with `distrobox`.

**Available Images:**
- `docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4` (Tracks `antirez` upstream)

```sh
toolbox create ds4-rocm-7.2.4 \
  --image docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4 \
  -- --device /dev/dri --device /dev/kfd \
  --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined

toolbox enter ds4-rocm-7.2.4
```

> [!TIP]
> Toolbox inherits your host's `PATH`, which may include `~/.local/bin`, `~/.cargo/bin`, etc. To avoid host binaries shadowing container ones, reset `PATH` after entering:
> ```sh
> export PATH=/usr/local/bin:/opt/rocm/bin:/usr/bin:/usr/sbin:/bin:/sbin
> ```

### 2. Download Model Weights

ds4 uses its own DeepSeek V4 Flash GGUFs from the [antirez/deepseek-v4-gguf](https://huggingface.co/antirez/deepseek-v4-gguf/tree/main) repository. Create a directory and download the model you need:

```sh
mkdir -p ~/ds4
```

> [!IMPORTANT]
> **Use the `imatrix` models.** Models labeled `chat-v2-imatrix` are quantized with an Importance Matrix calibrated on code and reasoning data. This preserves the logic and instruction-following pathways that matter most for coding agents, especially at extreme compressions like Q2. The non-imatrix variants (`chat-v2`) compress all weights uniformly and degrade faster on agentic tasks.

#### Single Node (128 GB RAM) — Recommended

The IQ2_XXS imatrix model (~80.8 GB) fits comfortably on a single Strix Halo node:

```sh
HF_XET_HIGH_PERFORMANCE=1 hf download antirez/deepseek-v4-gguf \
  DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --local-dir ~/ds4
```

#### Single Node — Hybrid Q2/Q4 (Higher Quality)

A hybrid model (~97 GB) that keeps later expert layers (37–42) at Q4 precision for better accuracy. It fits in 128 GB but leaves less room for context. Best suited for a **dedicated inference node** running a headless Linux distro (e.g. Fedora Server minimal) rather than a full desktop environment — you'll want every GB for the model and KV cache at `--ctx 120000`.

```sh
HF_XET_HIGH_PERFORMANCE=1 hf download antirez/deepseek-v4-gguf \
  DeepSeek-V4-Flash-Layers37-42Q4KExperts-OtherExpertLayersIQ2XXSGateUp-Q2KDown-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix-fixed.gguf \
  --local-dir ~/ds4
```

#### MTP Speculative Decoding Weights (Optional)

The MTP model (~3.6 GB) enables [speculative decoding](#speculative-decoding-mtp):

```sh
HF_XET_HIGH_PERFORMANCE=1 hf download antirez/deepseek-v4-gguf \
  DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf \
  --local-dir ~/ds4
```

### 3. Run Inference

**Interactive chat (multi-turn, thinking mode by default):**
```sh
ds4 -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 32768
```
Type at the `ds4>` prompt. `/nothink` for direct answers, `/help` for commands, Ctrl+C to interrupt generation.

**One-shot prompt:**
```sh
ds4 -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf -p "Explain Redis streams in one paragraph." --nothink
```

### 4. Run the Server

`ds4-server` exposes OpenAI and Anthropic-compatible HTTP endpoints. Inference is serialized through a single graph worker — concurrent requests queue, no batching.

**Using Toolbox/Distrobox (from inside the container):**
```sh
ds4-server -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 124000 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
```

**Using standard Docker/Podman:**
```sh
docker run --rm -it -p 8000:8000 \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  --ipc=host --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v ~/ds4:/models \
  kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4 \
  ds4-server -m /models/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 124000 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
```
*(Note: You can replace `docker` with `podman`. If you encounter permission issues when mounting the volume on systems with SELinux (like Fedora/RHEL), append `:z` to the mount: `-v ~/ds4:/models:z`).*


**Supported endpoints:**
- `POST /v1/chat/completions` — OpenAI chat (streaming, tools, thinking)
- `POST /v1/completions` — OpenAI completions
- `POST /v1/messages` — Anthropic-compatible (Claude Code style clients)
- `GET /v1/models`

**Quick test:**
```sh
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### KV Cache Disk Offloading

The `--kv-disk-dir` and `--kv-disk-space-mb` flags in the server examples above are **optional**. The server runs fine without them. When enabled, ds4 checkpoints the KV cache to disk as `<sha1>.kv` files keyed by the rendered prompt prefix. antirez calls this treating the KV cache as a **"first-class disk citizen"**.

**Why enable it:**
- **Prefix reuse** — coding agents resend the same system prompt every request. Disk caching skips re-prefill on matching prefixes, restoring from SSD instead of recomputing thousands of tokens.
- **Session persistence** — KV state survives server restarts and reboots.
- **Extend context beyond RAM** — inactive context parks on SSD, letting you use larger `--ctx` values than pure RAM would allow.

**Why skip it:** less SSD wear, simpler setup. Fine for one-off interactive use where you don't repeat prompts.

> [!IMPORTANT]
> **Strongly recommended for coding agents.** Without `--kv-disk-dir`, every request from Claude Code / opencode / Aider pays the full prefill cost. With it, only the first request is slow.

> [!NOTE]
> `/tmp` is cleared on reboot. For persistent checkpoints across reboots, use `~/.cache/ds4-kv` instead.

### 5. Benchmarking

`ds4-bench` measures prefill and generation throughput at context frontiers.

**Standard Benchmark:**
```sh
ds4-bench -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --prompt-file prompt.txt \
  --ctx-start 2048 \
  --ctx-max 65536 \
  --step-incr 2048 \
  --gen-tokens 128
```

### Speculative Decoding (MTP)

DeepSeek V4 models feature a Multi-Token Predictor (MTP) that can be used for speculative decoding to accelerate generation speed. You need to download the MTP weights (e.g., `DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf`) in addition to your main model.

To enable MTP, pass the `--mtp` flag pointing to the MTP GGUF file. You can also tune `--mtp-draft` (default 1) and `--mtp-margin` (default 3.0).

```sh
ds4-server -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --mtp ~/ds4/DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf \
  --mtp-draft 1 \
  --ctx 100000
```

### 6. Keep Updated

Refresh the local toolbox to the latest Docker Hub build:

```sh
./refresh-toolboxes.sh ds4-rocm-7.2.4
```

---

## Distributed Inference (Pipeline Parallelism)

The ROCm fork supports distributing the model across multiple nodes using pipeline parallelism (layer slicing). You can specify exactly which layers evaluate on which machine, designating one node as the `coordinator` and the others as `worker`s.

To run multi-node inference, you must use the `multi-node-rocm-7.2.4` container image (`ds4-multi-node-rocm-7.2.4` local toolbox), which contains the necessary patches for distributed networking and coordination.

### 1. Start the Worker (evaluates layers 22 through output)
Run the server on the worker node. Set the context size (e.g. `--ctx 262144` for 256k) and point it to the coordinator's IP and port:
```sh
ds4-server \
  -m /mnt/storage/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --role worker --layers 22:output \
  --coordinator 192.168.100.2 8081 \
  --ctx 262144
```

### 2. Start the Coordinator (evaluates layers 0 through 21)
Run the server on the coordinator node. Set the same context size (`--ctx 262144`), specify the MTP draft weights, roles, layer slicing, and listen on the coordinator's IP/port:
```sh
ds4-server \
  -m ~/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --ctx 262144 \
  --mtp ~/ds4/DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf \
  --mtp-draft 1 \
  --role coordinator --layers 0:21 \
  --listen 192.168.100.2 8081
```

### 3. Run Benchmarks from the Coordinator
To run throughput benchmarks across the cluster, first ensure all workers are running. Then, launch `ds4-bench` as the coordinator:
```sh
ds4-bench \
  -m ~/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --prompt-file ~/ds4/ds4/speed-bench/promessi_sposi.txt \
  --ctx-start 2048 --ctx-max 65536 --step-incr 2048 --gen-tokens 128 \
  --role coordinator --layers 0:21 \
  --listen 192.168.100.2 8081
```

---

## Using with Coding Agents

`ds4-server` can serve as the backend for local coding agents. Example **opencode** config (`~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ds4": {
      "name": "ds4.c (local)",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "dsv4-local"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek V4 Flash (ds4.c local)",
          "limit": {
            "context": 100000,
            "output": 384000
          }
        }
      }
    }
  }
}
```

With 128 GB RAM running the IQ2_XXS imatrix model (~81 GB), a context of 100k–300k tokens is practical. Full 1M context uses ~26 GB extra.

---

## Building Locally

```bash
# ROCm 7.2.4 (stable)
docker build -t ds4-rocm-7.2.4 -f toolboxes/Dockerfile.rocm-7.2.4 toolboxes/
```

---

## Stable Host Configuration

| Component | Recommended |
| :--- | :--- |
| OS | Fedora 42/43, Ubuntu 24.04+ |
| Kernel | 6.18.5+ |
| Firmware | Avoid `linux-firmware-20251125` (breaks ROCm). Use `20260110`+. |

