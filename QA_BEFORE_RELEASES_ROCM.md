# ROCm Release QA

This is the release gate for the ROCm/gfx1151 build used by
`strix-halo-ds4-toolbox`. It covers the two 128 GiB Strix Halo systems and the
models actually shipped through the cockpit.

Run only one large-model test at a time, except for the matching
worker/coordinator pair.

## Test topology

| Role | Host | Address | Model directory |
| --- | --- | --- | --- |
| Single host / coordinator | `fw2` | `192.168.100.2` | `/home/kyuz0/ds4` |
| Worker | `fw1` | `192.168.100.1` | `/mnt/storage/ds4` |

Toolbox tags are not interchangeable builds of one DS4 checkout. Each
Dockerfile selects its own repository and mutable branch:

| Toolbox tag | Dockerfile | DS4 repository | Branch | Target |
| --- | --- | --- | --- | --- |
| `rocm-7.2.4` | `Dockerfile.rocm-7.2.4` | `kyuz0/ds4` | `main` | Normal gfx1151 release |
| `multi-node-rocm-7.2.4` | `Dockerfile.multi-node-rocm-7.2.4` | `kyuz0/ds4` | `rocm-multi-node` | DeepSeek distributed |
| `glm-rocm-7.2.4` | `Dockerfile.glm-rocm-7.2.4` | `kyuz0/ds4` | `fix/rocm-distributed-glm` | GLM ROCm and GLM distributed |
| `gfx1201-rocm-7.2.4` | `Dockerfile.gfx1201-rocm-7.2.4` | `kyuz0/ds4` | `gfx1201-discrete-gpu` | gfx1201 only; outside this matrix |
| `rocm7-nightlies` | `Dockerfile.rocm7-nightlies` | `antirez/ds4` | `main` | Nightly ROCm; outside this matrix |

Check the Dockerfiles before every release. Do not infer an image's source from
its name or assume that two tags contain the same DS4 commit. The workflow
clones the branch tip during the build; record that tip before dispatching it.

For a toolbox release, use each model's image in the matrix below. For a
single DS4 code-change comparison, prefer one capable image built from that
exact commit for both baseline and candidate paths. Never describe a
cross-image result as a path-only comparison.

## Required matrix

| ID | Model | Mode | Toolbox tag | Hosts | Required settings |
| --- | --- | --- | --- | --- | --- |
| `DS-IQ2-R` | `DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf` | Resident | `rocm-7.2.4` | `fw2` | No `--ssd-streaming` |
| `DS-IQ2-S` | Same DeepSeek IQ2 | SSD streaming | `rocm-7.2.4` | `fw2` | `--ssd-streaming` |
| `GLM-S` | `GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf` | SSD streaming | `glm-rocm-7.2.4` | `fw2` | `--ssd-streaming` |
| `DS-Q4-S` | `DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf` | SSD streaming | `multi-node-rocm-7.2.4` | `fw2` | `--ssd-streaming` |
| `DS-Q4-D` | Same DeepSeek Q4 | Distributed | `multi-node-rocm-7.2.4` | `fw2` + `fw1` | `0:21 / 22:output`, chunk `4096`, window `2` |
| `GLM-D` | Same GLM IQ2 | Distributed | `glm-rocm-7.2.4` | `fw2` + `fw1` | `0:37 / 38:output`, chunk `256`, window `2` |

## 1. Build and deploy

For each Dockerfile in scope, inspect and record `ARG REPO` and `ARG BRANCH`,
then resolve the exact branch tip:

```sh
rg '^ARG (REPO|BRANCH)=' toolboxes/Dockerfile.*

git ls-remote https://github.com/kyuz0/ds4.git refs/heads/main
git ls-remote https://github.com/kyuz0/ds4.git refs/heads/rocm-multi-node
git ls-remote https://github.com/kyuz0/ds4.git refs/heads/fix/rocm-distributed-glm
```

Run the source repository's normal tests and whitespace gate at each recorded
commit. Then dispatch the three gfx1151 images:

```sh
gh workflow run build_and_publish.yml \
  --repo kyuz0/strix-halo-ds4-toolbox \
  --ref main \
  -f backends=rocm-7.2.4,multi-node-rocm-7.2.4,glm-rocm-7.2.4

gh run list \
  --repo kyuz0/strix-halo-ds4-toolbox \
  --workflow build_and_publish.yml \
  --limit 1

gh run watch RUN_ID \
  --repo kyuz0/strix-halo-ds4-toolbox \
  --exit-status
```

Pull the required images and record their IDs. For every distributed run, the
worker and coordinator IDs for that tag must match:

```sh
for TAG in rocm-7.2.4 multi-node-rocm-7.2.4 glm-rocm-7.2.4; do
  IMAGE="docker.io/kyuz0/strix-halo-ds4-toolbox:${TAG}"
  ssh fw1 podman pull "$IMAGE"
  ssh fw2 podman pull "$IMAGE"
  ssh fw1 podman image inspect "$IMAGE" --format '{{.Id}} {{.Created}}'
  ssh fw2 podman image inspect "$IMAGE" --format '{{.Id}} {{.Created}}'
done
```

Record model hashes. The copies used by both nodes must match:

```sh
ssh fw2 sha256sum \
  /home/kyuz0/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  /home/kyuz0/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  /home/kyuz0/ds4/GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf

ssh fw1 sha256sum \
  /mnt/storage/ds4/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  /mnt/storage/ds4/GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf
```

## 2. Podman setup

Run this on `fw2`:

```sh
ROCM_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4
MULTI_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:multi-node-rocm-7.2.4
GLM_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:glm-rocm-7.2.4
mkdir -p /tmp/ds4-rocm-qa
mkdir -p /tmp/ds4-rocm-qa/{DS-IQ2-R,DS-IQ2-S,GLM-S,DS-Q4-S,DS-Q4-D,GLM-D}-logits

run_fw2() {
  podman run --rm \
    --device /dev/dri \
    --device /dev/kfd \
    --group-add keep-groups \
    --security-opt seccomp=unconfined \
    --ipc=host \
    --cap-add=SYS_PTRACE \
    --security-opt label=disable \
    --userns=keep-id \
    --network=host \
    -v /home/kyuz0/ds4:/models:ro \
    -v /tmp/ds4-rocm-qa:/results \
    "$@"
}
```

Run this on `fw1`:

```sh
ROCM_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:rocm-7.2.4
MULTI_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:multi-node-rocm-7.2.4
GLM_IMAGE=docker.io/kyuz0/strix-halo-ds4-toolbox:glm-rocm-7.2.4
mkdir -p /tmp/ds4-rocm-qa

run_fw1() {
  podman run --rm \
    --device /dev/dri \
    --device /dev/kfd \
    --group-add keep-groups \
    --security-opt seccomp=unconfined \
    --ipc=host \
    --cap-add=SYS_PTRACE \
    --security-opt label=disable \
    --userns=keep-id \
    --network=host \
    -v /mnt/storage/ds4:/models:ro \
    -v /tmp/ds4-rocm-qa:/results \
    "$@"
}
```

## 3. Single-host benchmarks

Run the following template on `fw2` once for every single-host row below:

```sh
TEST_ID=DS-IQ2-R
MODEL=DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf
IMAGE=$ROCM_IMAGE
EXTRA_ARGS=()

run_fw2 \
  --name "ds4-qa-${TEST_ID}" \
  -e DS4_BENCH_DISABLE_SNAPSHOT=1 \
  "$IMAGE" \
  ds4-bench \
  --rocm \
  -m "/models/${MODEL}" \
  --prompt-file /models/ds4/speed-bench/promessi_sposi.txt \
  --ctx-start 512 \
  --ctx-max 4096 \
  --step-mul 2 \
  --ctx-alloc 4225 \
  --gen-tokens 64 \
  --show-output \
  --csv "/results/${TEST_ID}.csv" \
  --dump-frontier-logits-dir "/results/${TEST_ID}-logits" \
  "${EXTRA_ARGS[@]}" \
  2>&1 | tee "/tmp/ds4-rocm-qa/${TEST_ID}.log"
```

Use these values:

| ID | `IMAGE` | `MODEL` | `EXTRA_ARGS` |
| --- | --- | --- | --- |
| `DS-IQ2-R` | `$ROCM_IMAGE` | DeepSeek IQ2 filename above | `()` |
| `DS-IQ2-S` | `$ROCM_IMAGE` | DeepSeek IQ2 filename above | `(--ssd-streaming)` |
| `GLM-S` | `$GLM_IMAGE` | GLM filename above | `(--ssd-streaming)` |
| `DS-Q4-S` | `$MULTI_IMAGE` | DeepSeek Q4 filename above | `(--ssd-streaming)` |

For every run require:

- `ROCm backend initialized` and no CPU fallback;
- no crash, OOM, ROCm error, NaN, infinity, KV mismatch, or failed prefill;
- coherent output at every context;
- all requested rows in the CSV.

### DeepSeek IQ2 long-context decode regression

The short matrix above is the release smoke. Also run this resident DeepSeek
IQ2 sweep after changes to ROCm Q8 projections, attention output, hidden-state
mixing, or decode kernel selection:

```sh
run_fw2 \
  --name ds4-qa-ds-iq2-long \
  -e DS4_BENCH_DISABLE_SNAPSHOT=1 \
  "$ROCM_IMAGE" \
  ds4-bench \
  --rocm \
  -m /models/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf \
  --prompt-file /models/ds4/speed-bench/promessi_sposi.txt \
  --ctx-start 2048 \
  --ctx-max 65536 \
  --step-incr 2048 \
  --gen-tokens 128 \
  --show-output \
  --csv /results/DS-IQ2-R-long.csv \
  2>&1 | tee /tmp/ds4-rocm-qa/DS-IQ2-R-long.log
```

For a code-change comparison, run baseline and candidate images on the same
host with identical model bytes and arguments. Record both image IDs and
embedded DS4 commits. Compare every CSV row, including prefill t/s, generation
t/s, first-token latency, steady decode t/s, and KV bytes. A candidate that
improves early-context decode but regresses materially as the KV cache grows is
not a pass.

## 4. Distributed DeepSeek Q4

Set `IMAGE=$MULTI_IMAGE` on both hosts.

Start the worker on `fw1`:

```sh
run_fw1 \
  --name ds4-qa-ds-q4-worker \
  "$IMAGE" \
  ds4-server \
  -m /models/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --ctx 4225 \
  --role worker \
  --layers 22:output \
  --coordinator 192.168.100.2 8081 \
  --debug \
  2>&1 | tee /tmp/ds4-rocm-qa/DS-Q4-D-worker.log
```

Then run the coordinator benchmark on `fw2`:

```sh
run_fw2 \
  --name ds4-qa-ds-q4-coordinator \
  -e DS4_BENCH_DISABLE_SNAPSHOT=1 \
  "$IMAGE" \
  ds4-bench \
  -m /models/DeepSeek-V4-Flash-Q4KExperts-F16HC-F16Compressor-F16Indexer-Q8Attn-Q8Shared-Q8Out-chat-v2-imatrix.gguf \
  --prompt-file /models/ds4/speed-bench/promessi_sposi.txt \
  --ctx-start 512 \
  --ctx-max 4096 \
  --step-mul 2 \
  --ctx-alloc 4225 \
  --gen-tokens 64 \
  --show-output \
  --csv /results/DS-Q4-D.csv \
  --dump-frontier-logits-dir /results/DS-Q4-D-logits \
  --role coordinator \
  --layers 0:21 \
  --listen 192.168.100.2 8081 \
  --dist-prefill-chunk 512 \
  --dist-prefill-window 2 \
  --debug \
  2>&1 | tee /tmp/ds4-rocm-qa/DS-Q4-D-coordinator.log
```

Stop the worker after the benchmark.

## 5. Distributed GLM 5.2

Set `IMAGE=$GLM_IMAGE` on both hosts.

Start the worker on `fw1`:

```sh
run_fw1 \
  --name ds4-qa-glm-worker \
  -e DS4_GLM_MEMORY_GUARD_RESERVE_GB=8 \
  "$IMAGE" \
  ds4-server \
  -m /models/GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf \
  --ctx 4225 \
  --role worker \
  --layers 38:output \
  --coordinator 192.168.100.2 8081 \
  --debug \
  2>&1 | tee /tmp/ds4-rocm-qa/GLM-D-worker.log
```

Then run the coordinator benchmark on `fw2`:

```sh
run_fw2 \
  --name ds4-qa-glm-coordinator \
  -e DS4_GLM_MEMORY_GUARD_RESERVE_GB=8 \
  -e DS4_BENCH_DISABLE_SNAPSHOT=1 \
  "$IMAGE" \
  ds4-bench \
  -m /models/GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K.gguf \
  --prompt-file /models/ds4/speed-bench/promessi_sposi.txt \
  --ctx-start 512 \
  --ctx-max 4096 \
  --step-mul 2 \
  --ctx-alloc 4225 \
  --gen-tokens 64 \
  --show-output \
  --csv /results/GLM-D.csv \
  --dump-frontier-logits-dir /results/GLM-D-logits \
  --role coordinator \
  --layers 0:37 \
  --listen 192.168.100.2 8081 \
  --dist-prefill-chunk 256 \
  --dist-prefill-window 2 \
  --debug \
  2>&1 | tee /tmp/ds4-rocm-qa/GLM-D-coordinator.log
```

Require a complete route, coherent output, and no worker replay, KV mismatch,
route failure, or ROCm error. Stop the worker after the benchmark.

Scan the saved logs after the complete matrix; no match is expected:

```sh
rg -ni \
  'segmentation fault|ROCm error|prefill failed|evaluation failed|route (failed|incomplete)|KV.*mismatch|nan|infinity' \
  /tmp/ds4-rocm-qa/*.log
```

## 6. Quality gates

Use the scorer built from the exact DS4 commit under test. The production
toolbox image does not contain the scorer, so record the QA image ID and its
embedded DS4 commit separately.

Use:

- `gguf-tools/quality-testing/data/flash/manifest.tsv` for both DeepSeek files;
- `gguf-tools/quality-testing/data/glm52-openrouter-100/manifest.tsv` for GLM.

Run the tracked `score_official` scorer for:

1. `DS-IQ2-R`;
2. `DS-IQ2-S` with `--ssd-streaming`;
3. `DS-Q4-S` with `--ssd-streaming`;
4. `GLM-S` with `--ssd-streaming`.

Template:

```sh
score_official \
  MODEL.gguf \
  MANIFEST.tsv \
  /tmp/TEST_ID.tsv \
  4096 \
  OPTIONAL_SSD_FLAGS
```

Run the distributed-capable scorer used for the established 100-case
validation for `DS-Q4-D` and `GLM-D`. Start the matching worker first, then use
the same layer ranges and distributed settings as sections 4 and 5:

```sh
score_official_dist \
  MODEL.gguf \
  MANIFEST.tsv \
  /tmp/TEST_ID.tsv \
  4096 \
  --role coordinator \
  --layers START:END \
  --listen 192.168.100.2 8081 \
  --dist-prefill-chunk CHUNK \
  --dist-prefill-window 2
```

This distributed scorer is a local QA harness, not currently part of the
runtime toolbox. Its source and binary must be built from the same commit as
the worker. Do not replace it with one sampled chat answer.

Compare paired execution paths:

```sh
python3 gguf-tools/quality-testing/compare_scores.py \
  /tmp/DS-IQ2-R.tsv /tmp/DS-IQ2-S.tsv

python3 gguf-tools/quality-testing/compare_scores.py \
  /tmp/DS-Q4-S.tsv /tmp/DS-Q4-D.tsv

python3 gguf-tools/quality-testing/compare_scores.py \
  /tmp/GLM-S.tsv /tmp/GLM-D.tsv
```

Also compare complete frontier logits for each model that supports both SSD
streaming and distributed inference. These comparisons use identical model
bytes, prompt tokens, context frontiers, and the same model-specific toolbox
image; only the execution path changes:

```sh
for FRONTIER in 000512 001024 002048 004096; do
  python3 ~/ds4/ds4/speed-bench/compare_glm_validation.py logits \
    "/tmp/ds4-rocm-qa/DS-Q4-S-logits/frontier_${FRONTIER}.logits.json" \
    "/tmp/ds4-rocm-qa/DS-Q4-D-logits/frontier_${FRONTIER}.logits.json"

  python3 ~/ds4/ds4/speed-bench/compare_glm_validation.py logits \
    "/tmp/ds4-rocm-qa/GLM-S-logits/frontier_${FRONTIER}.logits.json" \
    "/tmp/ds4-rocm-qa/GLM-D-logits/frontier_${FRONTIER}.logits.json"
done
```

The comparison script is model-agnostic despite its GLM-oriented filename.
Record raw and centered cosine, relative RMSE, KL divergence, top-1 IDs, and
top-10/top-50 overlap. Exact floating-point equality is not required, but
top-1 should agree at every frontier and the distribution metrics should stay
close to the last accepted release. Investigate any abrupt divergence before
using scorer agreement as evidence that the execution paths are equivalent.

Release blockers:

- any non-finite logit or incomplete case;
- a frontier top-1 mismatch or unexplained large SSD/distributed logit
  divergence;
- a clear NLL, first-token, API top-1, or pair-order regression between paths;
- a large change from the last accepted result without an explained model or
  quantization change.

Last accepted GLM IQ2 comparison:

| Metric | SSD streaming | Distributed |
| --- | ---: | ---: |
| Cases | 100 | 100 |
| Scored tokens | 2,299 | 2,299 |
| Average NLL | 0.46919 | 0.46505 |
| First-token matches | 81 | 81 |
| API top-1 agreement | 86.010% | 86.190% |
| API pair-order agreement | 77.587% | 77.579% |

## 7. Cockpit gate

In `strix-halo-ds4-toolbox/ds4-strix-halo-cockpit`, select the
`glm-rocm-7.2.4` toolbox and inspect the final command before starting it.

| Selection | Expected command settings |
| --- | --- |
| GLM standalone | `--ssd-streaming`; no distributed flags |
| GLM coordinator | `--layers 0:37`, no `--ssd-streaming`, `--dist-prefill-chunk 256`, `--dist-prefill-window 2` |
| GLM worker | `--layers 38:output`, no coordinator-only prefill flags |
| DeepSeek Q4 standalone streaming | `--ssd-streaming` when its switch is enabled |
| DeepSeek Q4 coordinator | `--layers 0:21`, no `--ssd-streaming`, `--dist-prefill-chunk 512`, `--dist-prefill-window 2` |
| DeepSeek Q4 worker | `--layers 22:output` |

For GLM distributed mode, the cockpit should also select its model-specific
distributed context default (`30000`). Do not use SSD streaming together with
distributed residency.

Start one GLM distributed server pair through the cockpit and send:

```sh
wget --timeout=900 --tries=1 -qO- \
  --header='Content-Type: application/json' \
  --post-data='{"model":"glm-5.2","messages":[{"role":"user","content":"Reply with exactly: hello"}],"thinking":{"type":"disabled"},"max_tokens":16}' \
  http://localhost:8000/v1/chat/completions |
jq -r '.choices[0].message.content // .'
```

Require HTTP 200 and a coherent response.

## 8. Result tables

### Execution

| ID | Image ID | Model SHA-256 | Completed | Output coherent | Errors | Notes |
| --- | --- | --- | :---: | :---: | :---: | --- |
| `DS-IQ2-R` | | | | | | |
| `DS-IQ2-S` | | | | | | |
| `GLM-S` | | | | | | |
| `DS-Q4-S` | | | | | | |
| `DS-Q4-D` | | | | | | |
| `GLM-D` | | | | | | |

### Performance

| ID | Context | Prefill t/s | Decode t/s | First token ms | KV bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| | | | | | |

Last-known-good GLM figures on this topology are approximately:

| Mode | Context | Prefill t/s | Decode t/s |
| --- | ---: | ---: | ---: |
| Distributed | 4096 | 42.32 | 2.42 |
| Distributed suffix | 4096 to 8192 | 23.79 | 2.33 |
| SSD streaming | 4096 | 5.04 | 1.71 |
| SSD-streaming suffix | 4096 to 8192 | 2.95 | 1.62 |

The recorded SSD-streaming figures explicitly used
`--ssd-streaming-full-layers 0`; the release matrix above intentionally tests
the shipped automatic full-layer policy. Treat the figures as regression
indicators, not universal pass thresholds.

### Quality

| Pair | Cases | NLL delta | First-token delta | API top-1 delta | Pair-order delta | Pass |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| `DS-IQ2-R` vs `DS-IQ2-S` | | | | | | |
| `DS-Q4-S` vs `DS-Q4-D` | | | | | | |
| `GLM-S` vs `GLM-D` | 100 | | | | | |

### SSD/distributed frontier logits

| Pair | Frontiers | Top-1 agreement | Maximum KL | Minimum centered cosine | Pass |
| --- | --- | ---: | ---: | ---: | :---: |
| `DS-Q4-S` vs `DS-Q4-D` | 512, 1024, 2048, 4096 | | | | |
| `GLM-S` vs `GLM-D` | 512, 1024, 2048, 4096 | | | | |

## Sign-off

Do not sign off until:

- each distributed worker/coordinator pair uses the same image ID and model
  bytes;
- all six execution rows complete;
- all three quality comparisons are recorded;
- both SSD/distributed frontier-logit comparisons are recorded;
- the cockpit emits the expected model-specific flags;
- no skipped row is left without a reason.
