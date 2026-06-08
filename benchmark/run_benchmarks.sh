#!/usr/bin/env bash
set -e

# Navigate to the repo root to ensure consistent relative paths
cd "$(dirname "$0")/.."

# Configuration
MODEL_PATH="$HOME/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2.gguf"
PROMPT_PATH="./benchmark/promessi_sposi.txt"
RESULTS_DIR="./benchmark/results"
CTX_START=2048
CTX_MAX=65536
STEP_INCR=2048
GEN_TOKENS=128

TOOLBOXES=(
  "ds4-rocm-7.2.4"
  "ds4-rocm-7.2.4-ejpir"
)

mkdir -p "$RESULTS_DIR"

if [[ ! -f "$PROMPT_PATH" ]]; then
  echo "Error: Prompt file not found at $PROMPT_PATH"
  exit 1
fi

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Error: Model not found at $MODEL_PATH"
  exit 1
fi

for toolbox in "${TOOLBOXES[@]}"; do
  echo "========================================="
  echo "Running benchmark for $toolbox"
  echo "========================================="
  
  LOG_FILE="$RESULTS_DIR/${toolbox}.log"
  
  if [[ "$toolbox" == *"ejpir"* ]]; then
    CMD="DS4_SERVER_FAST_FULL=1 ds4-bench-fast"
  else
    CMD="ds4-bench"
  fi
  
  echo "Executing: toolbox run --container $toolbox bash -c \"$CMD -m '$MODEL_PATH' --prompt-file '$PROMPT_PATH' --ctx-start $CTX_START --ctx-max $CTX_MAX --step-incr $STEP_INCR --gen-tokens $GEN_TOKENS\""
  
  # Run via toolbox. The host path resolves transparently inside the toolbox.
  toolbox run --container "$toolbox" bash -c "$CMD -m '$MODEL_PATH' --prompt-file '$PROMPT_PATH' --ctx-start $CTX_START --ctx-max $CTX_MAX --step-incr $STEP_INCR --gen-tokens $GEN_TOKENS" > "$LOG_FILE" 2>&1 || true
  
  echo "Done. Results saved to $LOG_FILE"
done

echo "All benchmarks completed!"
