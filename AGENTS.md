# AI Agent Context: AMD Strix Halo ds4 Toolboxes

**Primary Goal:** This project provides pre-built containers ("toolboxes") for running the `ds4` inference backend optimally on AMD Ryzen AI Max "Strix Halo" APUs. It handles the environment configuration for ROCm 7.2.3 and ROCm 7 Nightlies, exposing compiled binary endpoints for LLM generation.

## Core Technologies
*   **Containerization**: [Toolbx](https://containertoolbx.org/) (Fedora) or Distrobox (Ubuntu/Debian). Underneath, Docker/Podman is used to build base images.
*   **Inference Engine**: [ds4](https://github.com/antirez/ds4) (Focusing on the `rocm` branch)
*   **Hardware / Drivers**: AMD "Strix Halo" APUs (Gfx1151). Supports ROCm 7.2.3 and ROCm 7 Nightlies.

## Repository Structure Overview
*   `/toolboxes/`: Dockerfiles used to build the container images:
    - `Dockerfile.rocm-7.2.3`: Configures stable ROCm 7.2.3 package repos.
    - `Dockerfile.rocm7-nightlies`: Queries and pulls developer ROCm 7 nightlies from the AMD S3 bucket.
*   `.github/workflows/`:
    - `build_and_publish.yml`: Automatically builds, runs smoke tests on compiled binaries (`ds4`, `ds4-server`, `ds4-bench`), and pushes tags to Docker Hub (`kyuz0/strix-halo-ds4-toolbox`).
    - `poll-ds4.yaml`: Checks upstream `antirez/ds4` repository's `rocm` branch for new commits every 4 hours, triggering a rebuild on changes.
    - `prune-old-toolboxes.yml`: Cleans up older timestamped builds from Docker Hub.
*   `refresh-toolboxes.sh`: Local convenience script to pull, recreate, and manage local container lifecycles.

## Critical Technical Quirks (Important for Development)
*   **Compilation translation**: The `ds4` ROCm backend is designed by using standard CUDA source files (`ds4_cuda.cu`) compiled with AMD's `hipcc` compiler. It defines CUDA-to-HIP macro translations in `ds4_rocm.h` under the `__HIP_PLATFORM_AMD__` block.
*   **Target GPU**: Strix Halo is compiled using `--offload-arch=gfx1151` (aliased as `ROCM_ARCH=gfx1151` in `ds4` Makefile).
*   **Host Kernel Parameters**: Optimal host configuration uses:
    `amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856`
    to allocate unified RAM and prevent GPU allocations from stalling.

## General Instructions for Coding Agents
1.  **Leanness**: Multi-stage docker builds should discard compilation headers and developer tool chains, only retaining built runtime binaries and necessary shared libraries in the final image.
2.  **Smoke Testing**: Every toolbox build must run help/version smoke tests for all three binary outputs (`ds4`, `ds4-server`, and `ds4-bench`) to ensure libraries link successfully.
3.  **Device Access**: Ensure `refresh-toolboxes.sh` passes `--device /dev/dri` and `--device /dev/kfd` alongside video/render group permissions for complete ROCm acceleration.
