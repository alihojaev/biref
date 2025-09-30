#!/usr/bin/env bash
set -euo pipefail

export HF_HOME=/workspace/huggingface
export PYTHONUNBUFFERED=1

if [[ "" != "" || "" != "" ]]; then
  python3 rp_handler.py | cat
else
  exec uvicorn app:app --host 0.0.0.0 --port 7865 --no-access-log
fi
