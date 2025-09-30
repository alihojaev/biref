#!/usr/bin/env bash
set -euo pipefail

export HF_HOME=/workspace/huggingface
export PYTHONUNBUFFERED=1

# Always run Runpod Serverless handler (like llama service)
exec python3 /workspace/rp_handler.py
