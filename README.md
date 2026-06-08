# AMD Strix Halo ds4 Toolboxes

Pre-built containers ("toolboxes") for running **[ds4](https://github.com/antirez/ds4)** — antirez's DeepSeek V4 Flash inference engine — on **AMD Ryzen AI Max "Strix Halo"** integrated GPUs (`gfx1151`).

The containers compile the `rocm` branch of `antirez/ds4` and expose the three compiled binaries: `ds4`, `ds4-server`, and `ds4-bench`. Toolbx is the standard developer container system on Fedora; Distrobox works on Ubuntu, Debian, Arch, openSUSE, etc.

---

## Supported Toolboxes

Pre-built images on Docker Hub: **[kyuz0/strix-halo-ds4-toolbox](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags)**

| Tag | Repository | Stack | Notes |
| :--- | :--- | :--- | :--- |
| `rocm-7.2.4` | [antirez/ds4](https://github.com/antirez/ds4) | ROCm 7.2.4 (stable) | Tracks `antirez` upstream. Recommended for most users. |
| `rocm-7.2.4-ejpir` | [ejpir/ds4-hip](https://github.com/ejpir/ds4-hip) | ROCm 7.2.4 (stable) | Experimental upstream-shape ROCm fork for high prefill performance on gfx1151. |

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
- `docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4-ejpir` (Tracks `ejpir` experimental upstream-shape ROCm fork for high prefill performance on gfx1151)

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

A hybrid model (~97 GB) that keeps later expert layers (37–42) at Q4 precision for better accuracy, while still fitting in 128 GB:

```sh
HF_XET_HIGH_PERFORMANCE=1 hf download antirez/deepseek-v4-gguf \
  DeepSeek-V4-Flash-Layers37-42Q4KExperts-OtherExpertLayersIQ2XXSGateUp-Q2KDown-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix-fixed.gguf \
  --local-dir ~/ds4
```

#### Dual Node (2× 128 GB RAM) — Q4

The full Q4 imatrix model (~153.3 GB) requires two Strix Halo nodes via [distributed inference](#distributed-inference-pipeline-parallelism). Download it on **both** machines:

```sh
HF_XET_HIGH_PERFORMANCE=1 hf download antirez/deepseek-v4-gguf \
  DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
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

```sh
ds4-server -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --ctx 100000 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
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

### ejpir Fork (High Performance)

The `rocm-7.2.4-ejpir` toolbox includes an experimental port by `@ejpir` that heavily optimizes the ROCm implementation towards upstream CUDA kernel shapes, specifically targeted at Strix Halo (`gfx1151`).

**Fast Wrapper Scripts:**
The image bundles optimized bash wrappers that automatically apply the `DS4_SERVER_FAST_FULL=1` environment variables needed for massive prefill speeds.

| Standard Binary | Fast Wrapper Script | Description |
| :--- | :--- | :--- |
| `ds4` | `ds4-fast` | Interactive chat CLI |
| `ds4-server` | `ds4-server-fast` | OpenAI-compatible server |
| `ds4-bench` | `ds4-bench-fast` | Throughput benchmarking tool |

**To achieve maximum prefill performance (~197–207 tok/s):**
1. It relies on ROCm 7.2.3/7.2.4.
2. It requires using full model copy rather than zero-copy.
3. High throughput is mostly observed when batched prefill kernels are saturated with larger prompts (e.g., 2048-token chunks).

Run the interactive CLI, benchmark, or server using the new `*-fast` wrapper scripts with the fast full preset by exporting `DS4_SERVER_FAST_FULL=1`:
```sh
DS4_SERVER_FAST_FULL=1 ds4-server-fast -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 131072 -n 65536
DS4_SERVER_FAST_FULL=1 ds4-bench-fast -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --prompt-file prompt.txt --ctx-start 2048 --ctx-max 65536 --step-incr 2048 --gen-tokens 128
```

### Distributed Inference (Pipeline Parallelism)

The ROCm fork supports distributing the model across multiple nodes using pipeline parallelism (layer slicing). You can specify exactly which layers evaluate on which machine, and designate one node as the `coordinator` and the others as `worker`s.

For example, to split the Q4 model between two machines (Coordinator: `192.168.100.2`, Worker: `192.168.100.1`):

**1. Start the Worker (evaluates layers 22 through output):**
```sh
DS4_SERVER_FAST_FULL=1 ds4-server-fast \
  -m ~/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --role worker --layers 22:output \
  --coordinator 192.168.100.2 8081 --debug
```

**2. Start the Coordinator (evaluates layers 0 through 21):**
```sh
DS4_SERVER_FAST_FULL=1 ds4-server-fast \
  -m ~/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --ctx 100072 -n 36000 \
  --role coordinator --layers 0:21 \
  --listen 192.168.100.2 8081 --debug
```

**Distributed Benchmarking:**
You can also use `ds4-bench-fast` as a coordinator to benchmark the entire cluster. First start the workers, then launch the benchmark:
```sh
DS4_SERVER_FAST_FULL=1 ds4-bench-fast \
  -m ~/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ctx-start 2048 --ctx-max 65536 --step-incr 2048 --gen-tokens 128 \
  --role coordinator --layers 0:21 \
  --listen 192.168.100.2 8081
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

> [!WARNING]
> **MTP is currently incompatible with Distributed Inference.**
> In a distributed setup where the worker handles the `output` layer, the worker returns only the final `logits` back to the coordinator over the network. MTP requires the final *hidden state* of the base model to operate, which remains stranded on the worker. Passing `--mtp` on the coordinator will currently fail to draft tokens.

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
