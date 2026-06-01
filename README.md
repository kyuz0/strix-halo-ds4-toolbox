# AMD Strix Halo ds4 Toolboxes

This project provides pre-built containers (“toolboxes”) for running the **DeepSeek ds4 backend** on **AMD Ryzen AI Max “Strix Halo”** integrated GPUs (architecture `gfx1151`). Toolbx is the standard developer container system in Fedora (and distrobox works on Ubuntu, Debian, openSUSE, Arch, etc).

---

### 📦 Project Context

These toolboxes compile the `rocm` branch of the `antirez/ds4` repository using ROCm 7.2.3 and ROCm 7 Nightlies. They expose three compiled backend binaries for hardware-accelerated inference:
- `ds4` (CLI / Interactive Chat Mode)
- `ds4-server` (OpenAI-compatible server)
- `ds4-bench` (Engine benchmarking utility)

---

## Table of Contents

- [Stable Configuration](#stable-configuration)
- [Supported Toolboxes](#supported-toolboxes)
- [Quick Start](#quick-start)
- [Host Configuration](#host-configuration)
- [Building Locally](#building-locally)

---

## Stable Configuration

- **OS**: Fedora 42/43 / Ubuntu 24.04+
- **Linux Kernel**: 6.18.5+
- **Linux Firmware**: Avoid `linux-firmware-20251125` (it breaks ROCm). Use `20260110` or newer.

---

## Supported Toolboxes

The pre-built containers are located on Docker Hub: [kyuz0/strix-halo-ds4-toolbox](https://hub.docker.com/r/kyuz0/strix-halo-ds4-toolbox/tags).

| Container Tag | Backend/Stack | Purpose / Notes |
| :--- | :--- | :--- |
| `rocm-7.2.3` | ROCm 7.2.3 | Latest stable 7.x build. Includes patch support for kernels 6.18.4+. |
| `rocm7-nightlies` | ROCm 7 Nightly | Tracks the latest ROCm 7 developer nightlies from AMD. |

---

## Quick Start

### 1. Create and Enter your Toolbox

**Ubuntu/Debian users:** Remember to replace `toolbox` with `distrobox` in the commands below.

```sh
# Create the toolbox container
toolbox create ds4-rocm-7.2.3 \
  --image docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.3 \
  -- --device /dev/dri --device /dev/kfd \
  --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined

# Enter the toolbox
toolbox enter ds4-rocm-7.2.3
```

### 2. Run Inference or Server Mode

Inside the toolbox, you can call the binaries directly. Make sure to download a compatible DeepSeek GGUF model (e.g. `ds4flash.gguf` or others).

**Interactive CLI mode:**
```sh
ds4 --model models/ds4flash.gguf --ctx 32768
```

**Server mode (OpenAI API compatible):**
```sh
ds4-server --model models/ds4flash.gguf --ctx 32768 --host 0.0.0.0 --port 8080
```

**Benchmarking mode:**
```sh
ds4-bench --prompt-file prompt.txt --model models/ds4flash.gguf
```

### 3. Keep Updated

You can refresh your local toolboxes to the latest Docker Hub builds using the helper script:

```sh
./refresh-toolboxes.sh all
```

---

## Host Configuration

Strix Halo uses unified memory. Add these kernel/boot parameters to your GRUB configuration to enable unified memory and allocate up to 124 GiB for the iGPU:

`amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856`

Apply with:
```bash
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo reboot
```

---

## Building Locally

If you want to build the containers manually on your system:

```bash
# Build ROCm 7.2.3 version
docker build -t ds4-rocm-7.2.3 -f toolboxes/Dockerfile.rocm-7.2.3 toolboxes/

# Build ROCm 7 Nightlies version
docker build -t ds4-rocm7-nightlies -f toolboxes/Dockerfile.rocm7-nightlies toolboxes/
```
