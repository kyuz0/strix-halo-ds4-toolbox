#!/bin/bash

# A script to measure GPU vs CPU drift across different context lengths.
# It ensures that the argmax (top token) remains identical even as context grows.

MODEL="${1:-~/ds4/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf}"

# A long prompt to ensure we have enough tokens to test up to 256+ tokens
LONG_PROMPT="In computer science, floating-point arithmetic is formulaic representation of real numbers as an approximation to support a trade-off between range and precision. For this reason, floating-point computation is often found in systems which include very small and very large real numbers, which require fast processing times. A number is, in general, represented approximately to a fixed number of significant digits and scaled using an exponent in some fixed base; the base for the scaling is normally two, ten, or sixteen. A number that can be represented exactly is of the following form: significand multiplied by base raised to the power of exponent. As context grows in large language models, these small floating-point approximation errors can accumulate across thousands of sequential matrix multiplications. Deep learning architectures like Mixture of Experts amplify these differences because slightly divergent hidden states might route tokens to different experts, cascading the drift. However, so long as the relative distribution remains stable, the absolute argmax will remain consistent and the model will not hallucinate. This script empirically verifies this property by testing various prompt lengths and asserting that the CPU reference implementation and the hardware-accelerated GPU implementation agree on the top token prediction."

echo "Testing drift on model: $MODEL"
echo "--------------------------------------------------------------------------------------------"
printf "%-8s | %-12s | %-12s | %-8s | %-8s | %-12s | %-12s | %-10s\n" "Tokens" "Max Drift" "RMS Drift" "CPU Top" "GPU Top" "Top20 Match" "KL Div" "Argmax Match"
echo "--------------------------------------------------------------------------------------------"

# Token lengths to test
TOKEN_COUNTS=(4 8 16 32 64 128 256)

for tokens in "${TOKEN_COUNTS[@]}"; do
    # Run the test
    output=$(DS4_SERVER_FAST_FULL=1 DS4_METAL_GRAPH_PROMPT_TOKENS=$tokens ds4-fast \
        -m "$MODEL" \
        -p "$LONG_PROMPT" \
        --metal-graph-prompt-test 2>&1 | grep "logits:")

    if [[ -z "$output" ]]; then
        echo "Error running test for $tokens tokens. Is the model path correct?"
        exit 1
    fi

    # Parse the output
    # Example output: ds4: Metal prompt graph logits: tokens=18 logits_max=4.23758 logits_rms=0.734869 cpu_top=2581 gpu_top=2581 cpu_top_logit=35.828 gpu_top_logit=36.7067 top20_match=19/20 kl_div=0.0001
    actual_tokens=$(echo "$output" | grep -oP 'tokens=\K\d+')
    logits_max=$(echo "$output" | grep -oP 'logits_max=\K[\d.]+')
    logits_rms=$(echo "$output" | grep -oP 'logits_rms=\K[\d.]+')
    cpu_top=$(echo "$output" | grep -oP 'cpu_top=\K\d+')
    gpu_top=$(echo "$output" | grep -oP 'gpu_top=\K\d+')
    top20_match=$(echo "$output" | grep -oP 'top20_match=\K[0-9/]+')
    kl_div=$(echo "$output" | grep -oP 'kl_div=\K[0-9e.-]+')

    match="❌ FAIL"
    if [[ "$cpu_top" == "$gpu_top" ]]; then
        match="✅ PASS"
    fi

    printf "%-8s | %-12s | %-12s | %-8s | %-8s | %-12s | %-12s | %-10s\n" "$actual_tokens" "$logits_max" "$logits_rms" "$cpu_top" "$gpu_top" "${top20_match:-N/A}" "${kl_div:-N/A}" "$match"

    # Stop if we hit a mismatch
    if [[ "$match" == "❌ FAIL" ]]; then
        echo "------------------------------------------------------------------"
        echo "CATASTROPHIC DRIFT DETECTED: Argmax mismatch at $actual_tokens tokens!"
        exit 1
    fi
done

echo "------------------------------------------------------------------"
echo "All tests passed successfully. The GPU argmax is perfectly stable!"
