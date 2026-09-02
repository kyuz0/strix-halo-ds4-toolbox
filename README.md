# AMD Strix Halo ds4 Toolbox

A pre-built container image ("toolbox") for running **[ds4](https://github.com/antirez/ds4)** — antirez's DeepSeek V4 Flash inference engine — on **AMD Ryzen AI Max "Strix Halo"** integrated GPUs (`gfx1151`).

> [!IMPORTANT]
> This repository is part of the **[Strix Halo AI Toolboxes](https://strix-halo-toolboxes.com/)** project. Follow the central guide for the recommended host setup, including unified-memory allocation and OS-specific configuration.

## Recommended setup: AI Toolbox Cockpit

[AI Toolbox Cockpit](https://github.com/kyuz0/ai-toolbox-cockpit) is the preferred way to install, launch, and update these containers. It provides tested, pre-configured profiles; supports Toolbx and Distrobox; and can run ds4 directly with Podman or Docker, so Toolbx is not required.

```bash
pipx install git+https://github.com/kyuz0/ai-toolbox-cockpit.git
ai-toolbox-cockpit
```

The repository's [`refresh-toolboxes.sh`](refresh-toolboxes.sh) remains available for manual Toolbx refreshes. The Cockpit is recommended for normal installation and updates.

The `rocm-10.0` container is based on the
[`perf/rocm-gfx1151-mmq-kernel-lab`](https://github.com/kyuz0/ds4/tree/perf/rocm-gfx1151-mmq-kernel-lab)
branch of [`kyuz0/ds4`](https://github.com/kyuz0/ds4) and compiled against
**ROCm 10.0 (stable)**. It exposes three compiled binaries: `ds4`,
`ds4-server`, and `ds4-bench`.

* **Docker Hub Image:** [kyuz0/strix-halo-ds4-toolbox:rocm-10.0](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags)

## Available images

- `docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-10.0` — stable ROCm 10.0 build tracking `kyuz0/ds4:perf/rocm-gfx1151-mmq-kernel-lab`.
- `docker.io/kyuz0/strix-halo-ds4-toolbox:therock-nightly` — experimental build tracking the latest TheRock multi-architecture `gfx1151` nightly and `antirez/ds4:main`.
- `docker.io/kyuz0/strix-halo-ds4-toolbox:gfx1201-rocm-7.14` — ROCm 7.14 build for AMD Radeon AI PRO R9700 (`gfx1201`); it is not a Strix Halo image.

---

## 📺 Video Demo

[![Watch the YouTube Video](https://i.ytimg.com/vi/Cfl3TS7ME5s/maxresdefault.jpg)](https://youtu.be/Cfl3TS7ME5s)

---

## Manual setup and usage

Use this section only if you prefer to manage the container and commands yourself. For the guided, tested path across Toolbx, Distrobox, Podman, and Docker, use [AI Toolbox Cockpit](#recommended-setup-ai-toolbox-cockpit).

### 1. Create and Enter the Toolbox

The example below uses Toolbx. See the [central Strix Halo setup guide](https://strix-halo-toolboxes.com/) for host preparation and other supported container engines.

```sh
toolbox create ds4-rocm-10.0 \
  --image docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-10.0 \
  -- --device /dev/dri --device /dev/kfd \
  --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined

toolbox enter ds4-rocm-10.0
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

This model leaves less memory headroom for ROCm graph buffers. At long contexts,
start it with `--prefill-chunk 2048`; see [Prefill Chunk Size](#prefill-chunk-size).

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
ds4-server -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 124000
```

**Using standard Docker/Podman:**
```sh
docker run --rm -it -p 8000:8000 \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  --ipc=host --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v ~/ds4:/models:ro \
  kyuz0/strix-halo-ds4-toolbox:rocm-10.0 \
  ds4-server -m /models/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf --ctx 124000
```
*(Note: You can replace `docker` with `podman`. If you encounter permission issues when mounting volumes on systems with SELinux (like Fedora/RHEL), add `z` to each volume option, for example `-v ~/ds4:/models:ro,z`.)*


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

### Prefill Chunk Size

`--prefill-chunk N` sets the maximum number of prompt tokens processed in one
GPU prefill batch. It does **not** limit the context length. Smaller chunks use
less ROCm graph and scratch memory, but may reduce prefill throughput because
the prompt is processed in more batches.

For DeepSeek V4 Flash, ds4 automatically uses 4096-token chunks for contexts
larger than 4096 tokens. The ~97 GB hybrid Q2/Q4 model has much less memory
headroom on a 128 GB Strix Halo system, so 2048 is the recommended starting
point for long contexts:

```sh
ds4-server -m ~/ds4/DeepSeek-V4-Flash-Layers37-42Q4KExperts-OtherExpertLayersIQ2XXSGateUp-Q2KDown-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix-fixed.gguf \
  --ctx 64000 \
  --prefill-chunk 2048
```

The same option works with the interactive `ds4` CLI and `ds4-bench`. Try 2048 if the default
4096 OOMs during startup or long-context prefill. Leave the option unset to use
ds4's automatic model-specific default.

AI Toolbox Cockpit applies 2048 automatically when the curated ~97 GB hybrid model is selected, while keeping the field editable. Other models remain on Auto.

### KV Disk Cache (Optional)

Disk caching is disabled by default. Enable it with `--kv-disk-dir` and
`--kv-disk-space-mb` when useful. ds4 checkpoints KV state as `<sha1>.kv` files
keyed by the rendered prompt prefix—what antirez calls treating the KV cache as
a **"first-class disk citizen"**.

**Why enable it:**
- **Prefix reuse** — coding agents resend the same system prompt every request. Disk caching skips re-prefill on matching prefixes, restoring from SSD instead of recomputing thousands of tokens.
- **Session persistence** — KV state survives server restarts and reboots.
- **Session switching** — checkpoints for inactive conversations can be restored later without keeping multiple live KV caches in memory.

**Why skip it:** less SSD wear, simpler setup. Fine for one-off interactive use where you don't repeat prompts.

> [!IMPORTANT]
> Disk caching does not reduce the memory allocated for the active context and
> does not make an otherwise-too-large `--ctx` fit in RAM. It is a checkpoint
> and resume mechanism for matching prompt prefixes.

For Toolbox/Distrobox, choose a persistent directory in your shared home:

```sh
mkdir -p ~/.cache/ds4-kv
ds4-server -m ~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --ctx 124000 \
  --kv-disk-dir ~/.cache/ds4-kv \
  --kv-disk-space-mb 8192
```

With standard Docker/Podman, bind-mount the host cache into the disposable
container and pass the container path to ds4:

```sh
mkdir -p ~/.cache/ds4-kv
docker run --rm -it -p 8000:8000 \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  --ipc=host --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v ~/ds4:/models:ro \
  -v ~/.cache/ds4-kv:/var/cache/ds4-kv \
  kyuz0/strix-halo-ds4-toolbox:rocm-10.0 \
  ds4-server -m /models/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
    --ctx 124000 \
    --kv-disk-dir /var/cache/ds4-kv \
    --kv-disk-space-mb 8192
```

> [!NOTE]
> AI Toolbox Cockpit performs this host-directory mount automatically when its KV Disk Cache switch is enabled.

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

AI Toolbox Cockpit is the recommended update path. If you created the Toolbx container manually, refresh it to the latest Docker Hub build with:

```sh
./refresh-toolboxes.sh ds4-rocm-10.0
```

---

## Distributed Inference (Pipeline Parallelism)

The ROCm fork supports distributing the model across multiple nodes using pipeline parallelism (layer slicing). You can specify exactly which layers evaluate on which machine, designating one node as the `coordinator` and the others as `worker`s.

Multi-node inference is included in the standard `rocm-10.0` image (`ds4-rocm-10.0` local toolbox).

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
# ROCm 10.0 (stable)
docker build -t ds4-rocm-10.0 -f toolboxes/Dockerfile.rocm-10.0 toolboxes/
```
