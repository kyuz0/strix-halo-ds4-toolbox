# AMD Strix Halo ds4 Toolboxes

Pre-built containers ("toolboxes") for running **[ds4](https://github.com/antirez/ds4)** — antirez's DeepSeek V4 Flash inference engine — on **AMD Ryzen AI Max "Strix Halo"** integrated GPUs (`gfx1151`).

The containers compile the `rocm` branch of `antirez/ds4` and expose the three compiled binaries: `ds4`, `ds4-server`, and `ds4-bench`. Toolbx is the standard developer container system on Fedora; Distrobox works on Ubuntu, Debian, Arch, openSUSE, etc.

---

## Supported Toolboxes

Pre-built images on Docker Hub: **[kyuz0/strix-halo-ds4-toolbox](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags)**

| Tag | Stack | Notes |
| :--- | :--- | :--- |
| `rocm-7.2.3` | ROCm 7.2.3 (stable) | Recommended for most users. |
| `rocm7-nightlies` | ROCm 7 Nightly | Tracks latest AMD developer nightlies. |

---

## Host Configuration

Strix Halo uses unified memory. Add these kernel boot parameters to allocate up to 124 GiB for the iGPU:

```
amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856
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
- `docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4-alantsev` (Tracks `alantsev` fork with newer features)
- `docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4-ejpir` (Tracks `ejpir` experimental upstream-shape ROCm fork for high prefill performance on gfx1151)

```sh
toolbox create ds4-rocm-7.2.4 \
  --image docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4 \
  -- --device /dev/dri --device /dev/kfd \
  --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined

toolbox enter ds4-rocm-7.2.4
```

### 2. Download Model Weights

ds4 only works with its own DeepSeek V4 Flash GGUFs. The `download_model.sh` script is included in the toolbox:

```sh
download_model.sh q2-imatrix    # ~81 GB, recommended for 96/128 GB RAM
# download_model.sh q4-imatrix  # ~153 GB, for >= 256 GB RAM
```

Models are saved to `./gguf/` and `./ds4flash.gguf` is symlinked to the download. See the [model repo](https://huggingface.co/antirez/deepseek-v4-gguf) for all available quants.

### 3. Run Inference

**Interactive chat (multi-turn, thinking mode by default):**
```sh
ds4 -m ds4flash.gguf --ctx 32768
```
Type at the `ds4>` prompt. `/nothink` for direct answers, `/help` for commands, Ctrl+C to interrupt generation.

**One-shot prompt:**
```sh
ds4 -m ds4flash.gguf -p "Explain Redis streams in one paragraph." --nothink
```

### 4. Run the Server

`ds4-server` exposes OpenAI and Anthropic-compatible HTTP endpoints. Inference is serialized through a single graph worker — concurrent requests queue, no batching.

```sh
ds4-server -m ds4flash.gguf --ctx 100000 \
  --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
```

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

### 5. Benchmarking

`ds4-bench` measures prefill and generation throughput at context frontiers. Make sure to use `DS4_CUDA_COPY_MODEL_CHUNKED=1` to optimize model loading on Strix Halo.

**Standard Benchmark:**
```sh
DS4_CUDA_COPY_MODEL_CHUNKED=1 ds4-bench -m ds4flash.gguf \
  --prompt-file prompt.txt \
  --ctx-start 2048 \
  --ctx-max 65536 \
  --step-incr 2048 \
  --gen-tokens 128
```

### ejpir Fork (High Performance)

The `rocm-7.2.4-ejpir` toolbox includes an experimental port by `@ejpir` that heavily optimizes the ROCm implementation towards upstream CUDA kernel shapes, specifically targeted at Strix Halo (`gfx1151`).

**To achieve maximum prefill performance (~197–207 tok/s):**
1. It relies on ROCm 7.2.3/7.2.4.
2. It requires using full model copy rather than zero-copy.
3. High throughput is mostly observed when batched prefill kernels are saturated with larger prompts (e.g., 2048-token chunks).

Run the interactive CLI or server with the fast full preset by exporting `DS4_SERVER_FAST_FULL=1`:
```sh
DS4_SERVER_FAST_FULL=1 ds4-server -m ds4flash.gguf --ctx 131072
```

### 6. Keep Updated

Refresh local toolboxes to the latest Docker Hub builds:

```sh
./refresh-toolboxes.sh all
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

With 128 GB RAM running q2 quants (~81 GB), a context of 100k–300k tokens is practical. Full 1M context uses ~26 GB extra.

---

## Building Locally

```bash
# ROCm 7.2.3 (stable)
docker build -t ds4-rocm-7.2.3 -f toolboxes/Dockerfile.rocm-7.2.3 toolboxes/

# ROCm 7 Nightlies
docker build -t ds4-rocm7-nightlies -f toolboxes/Dockerfile.rocm7-nightlies toolboxes/
```

---

## Stable Host Configuration

| Component | Recommended |
| :--- | :--- |
| OS | Fedora 42/43, Ubuntu 24.04+ |
| Kernel | 6.18.5+ |
| Firmware | Avoid `linux-firmware-20251125` (breaks ROCm). Use `20260110`+. |
