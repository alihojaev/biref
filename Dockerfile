# CUDA 12.1 runtime with PyTorch 2.1.2 similar to dalle service
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        wget \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install extra libs (xformers often helps with attention memory)
RUN python3 -m pip install --upgrade pip setuptools wheel \
    && python3 -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
        xformers==0.0.23.post1

# Copy requirements first for caching
COPY requirements.txt /workspace/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /workspace/requirements.txt

# Clone and install BiRefNet (ToonOut fork maintains original structure)
# We install as editable to import birefnet.*
RUN git clone --depth=1 https://github.com/MatteoKartoon/BiRefNet.git /workspace/BiRefNet \
    && python3 -m pip install -e /workspace/BiRefNet

# Setup HF cache
ARG HF_TOKEN=""
ENV HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
ENV HF_HOME=/workspace/huggingface
RUN mkdir -p ${HF_HOME}

# Pre-download ToonOut weights if possible (non-fatal)
RUN python3 - <<'PY' || true
import os
from huggingface_hub import hf_hub_download
repo='joelseytre/toonout'
cache=os.environ.get('HF_HOME')
for fname in ['model.safetensors','model.ckpt','pytorch_model.bin']:
    try:
        p = hf_hub_download(repo_id=repo, filename=fname, cache_dir=cache)
        print('Downloaded', p)
        break
    except Exception as e:
        print('Skip', fname, e)
PY

# Copy app files
COPY app.py /workspace/app.py
COPY rp_handler.py /workspace/rp_handler.py
COPY start.sh /workspace/start.sh
RUN chmod +x /workspace/start.sh

EXPOSE 7865

CMD ["/workspace/start.sh"]
