#!/usr/bin/env bash

set -e

# List of all known toolboxes and their configurations
# Group flags are added later based on the container engine, so they are
# deliberately absent from these option strings.
declare -A TOOLBOXES

TOOLBOXES["ds4-rocm-10.0"]="docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-10.0 --device /dev/dri --device /dev/kfd --security-opt seccomp=unconfined"
TOOLBOXES["ds4.1f-rocm10.0"]="docker.io/kyuz0/strix-halo-ds4-toolbox:ds4.1f-rocm10.0 --device /dev/dri --device /dev/kfd --security-opt seccomp=unconfined"
TOOLBOXES["ds4-gfx1201-rocm-7.14"]="docker.io/kyuz0/strix-halo-ds4-toolbox:gfx1201-rocm-7.14 --device /dev/dri --device /dev/kfd --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined"
TOOLBOXES["ds4-therock-nightly"]="docker.io/kyuz0/strix-halo-ds4-toolbox:therock-nightly --device /dev/dri --device /dev/kfd --group-add video --group-add render --group-add sudo --security-opt seccomp=unconfined"

# Toolboxes built with RoCE (verbs) support. Only these get /dev/infiniband
# passed through; the other images have no RDMA code path.
ROCE_TOOLBOXES=("ds4-rocm-10.0" "ds4.1f-rocm10.0")

function usage() {
  echo "Usage: $0 [all|toolbox-name1 toolbox-name2 ...]"
  echo "Available toolboxes:"
  for name in "${!TOOLBOXES[@]}"; do
    echo "  - $name"  
  done
  exit 1
}

# Check OS and set appropriate toolbox command
ENGINE="docker"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  if [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
    TOOLBOX_CMD="distrobox"
  else
    TOOLBOX_CMD="toolbox"
  fi
fi

# Resolve the underlying container engine. Podman resolves --group-add by name
# inside the image, which does not match the host video/render GIDs needed for
# /dev/kfd, so podman gets keep-groups instead. Docker keeps named groups.
if [ "$TOOLBOX_CMD" = "toolbox" ]; then
  ENGINE="podman"
elif [ -n "${DISTROBOX_ENGINE:-}" ]; then
  ENGINE="$DISTROBOX_ENGINE"
elif command -v podman > /dev/null; then
  ENGINE="podman"
fi

if [ "$ENGINE" = "podman" ]; then
  GROUP_FLAGS="--group-add keep-groups --group-add sudo"
else
  GROUP_FLAGS="--group-add video --group-add render --group-add sudo"
fi
echo "ℹ️  Engine: $ENGINE ($GROUP_FLAGS)"

# RoCE/RDMA passthrough: only meaningful when the host exposes verbs devices.
RDMA_FLAGS=""
if [ -d /dev/infiniband ]; then
  echo "🔎 InfiniBand devices detected. Adding RoCE passthrough."
  RDMA_FLAGS="--device /dev/infiniband --ulimit memlock=-1"
else
  echo "ℹ️  No /dev/infiniband on this host; RoCE passthrough skipped."
fi

# Check dependencies
DEPENDENCIES=("podman" "$TOOLBOX_CMD")
for cmd in "${DEPENDENCIES[@]}"; do
  if ! command -v "$cmd" > /dev/null; then
    if [ "$cmd" = "distrobox" ]; then
      echo "Error: 'distrobox' is not installed. Debian-based distributions (like Ubuntu) must use distrobox instead of toolbox." >&2
      echo "Please install distrobox (e.g., sudo apt install distrobox) and try again." >&2
    else
      echo "Error: '$cmd' is not installed." >&2
    fi
    exit 1
  fi
done

if [ "$#" -lt 1 ]; then
  usage
fi

# Determine which toolboxes to refresh
if [ "$1" = "all" ]; then
  SELECTED_TOOLBOXES=("${!TOOLBOXES[@]}")
else
  SELECTED_TOOLBOXES=()
  for arg in "$@"; do
    if [[ -v TOOLBOXES["$arg"] ]]; then
      SELECTED_TOOLBOXES+=("$arg")
    else
      echo "Error: Unknown toolbox '$arg'"
      usage
    fi
  done
fi

# Loop through selected toolboxes
for name in "${SELECTED_TOOLBOXES[@]}"; do
  config="${TOOLBOXES[$name]}"
  image=$(echo "$config" | awk '{print $1}')
  options="${config#* }"

  # Only the ROCm 10.0 images are engine-aware; the others keep their literal
  # options exactly as before.
  for roce in "${ROCE_TOOLBOXES[@]}"; do
    if [ "$roce" = "$name" ]; then
      options="$options $GROUP_FLAGS"
      if [ -n "$RDMA_FLAGS" ]; then
        options="$options $RDMA_FLAGS"
        echo "📡 RoCE enabled for $name (verify inside with: ulimit -l, ibv_devinfo)"
      fi
      break
    fi
  done

  echo "🔄 Refreshing $name (image: $image)"

  # Remove the toolbox if it exists
  if $TOOLBOX_CMD list | grep -q "$name"; then
    echo "🧹 Removing existing toolbox: $name"
    $TOOLBOX_CMD rm -f "$name"
  fi

  echo "⬇️ Pulling latest image: $image"
  podman pull "$image"

  echo "📦 Recreating toolbox: $name"
  $TOOLBOX_CMD create "$name" --image "$image" -- $options

  # --- Cleanup: remove dangling images ---
  repo="${image%:*}"

  # Remove dangling images from this repository (typically prior pulls of this tag)
  while read -r id; do
    podman image rm -f "$id" >/dev/null 2>&1 || true
  done < <(podman images --format '{{.ID}} {{.Repository}}:{{.Tag}}' \
           | awk -v r="$repo" '$2==r":<none>" {print $1}')
  # --- end cleanup ---

  echo "✅ $name refreshed"
  echo
done
