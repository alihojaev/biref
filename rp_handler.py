import base64
import io
import os
from typing import Any, Dict, Optional

import runpod
from PIL import Image
import numpy as np
import torch

HF_CACHE_DIR = os.getenv('HF_HOME', '/workspace/huggingface')
HF_TOONOUT_MODEL = 'joelseytre/toonout'

_biref_model = None
_device = 'cuda' if torch.cuda.is_available() else 'cpu'


def _ensure_rgba(img: Image.Image) -> Image.Image:
    if img.mode != 'RGBA':
        return img.convert('RGBA')
    return img


def _b64_to_image(b64: str) -> Image.Image:
    if b64.startswith('data:') and ';base64,' in b64:
        b64 = b64.split(',', 1)[1]
    padding = (4 - len(b64) % 4) % 4
    b = base64.b64decode(b64 + ('=' * padding))
    img = Image.open(io.BytesIO(b))
    return img


def _image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _load_birefnet():
    global _biref_model
    if _biref_model is not None:
        return _biref_model
    try:
        # Import BiRefNet from installed package
        from birefnet.models.birefnet import BiRefNet  # type: ignore
        from huggingface_hub import hf_hub_download

        # Try to fetch ToonOut weights from HF with common filenames
        possible_files = [
            'model.safetensors',
            'model.ckpt',
            'pytorch_model.bin'
        ]
        ckpt_path = None
        for fname in possible_files:
            try:
                ckpt_path = hf_hub_download(repo_id=HF_TOONOUT_MODEL, filename=fname, cache_dir=HF_CACHE_DIR)
                break
            except Exception:
                continue
        if ckpt_path is None:
            raise RuntimeError('Failed to download ToonOut weights')

        try:
            model = BiRefNet()
        except Exception:
            model = BiRefNet(backbone='mit_b5')

        state = torch.load(ckpt_path, map_location='cpu')
        if isinstance(state, dict) and 'state_dict' in state:
            state = state['state_dict']
        try:
            model.load_state_dict(state, strict=False)
        except Exception:
            # Some forks nest weights differently; ignore missing keys
            missing, unexpected = model.load_state_dict(state, strict=False)
        model.eval().to(_device)
        _biref_model = model
        return model
    except Exception as e:
        # Fallback: use rembg (U2Net/ONNX) if BiRefNet unavailable
        _biref_model = 'fallback'
        return 'fallback'


def _infer_rgba(image: Image.Image) -> Image.Image:
    model = _load_birefnet()
    if model == 'fallback':
        from rembg import remove
        arr = np.array(image.convert('RGBA'))
        out = remove(arr)
        return Image.fromarray(out)

    import torchvision.transforms as T  # provided by base PyTorch image
    with torch.no_grad():
        img_rgb = image.convert('RGB')
        tr = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        ])
        tensor = tr(img_rgb).unsqueeze(0).to(_device)
        pred = model(tensor)
        if isinstance(pred, dict):
            for k in ['pred', 'alpha', 'out', 'mask']:
                if k in pred:
                    pred = pred[k]
                    break
        if isinstance(pred, (list, tuple)):
            pred = pred[-1]
        prob = torch.sigmoid(pred.float()).squeeze().clamp(0, 1).cpu().numpy()
        if prob.ndim == 3 and prob.shape[0] in (1, 3):
            prob = prob[0]
        alpha = (prob * 255.0).astype(np.uint8)
        rgba = np.dstack([np.array(img_rgb), alpha])
        return Image.fromarray(rgba, mode='RGBA')


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = (event or {}).get('input', {})
        image_b64: Optional[str] = payload.get('image')
        return_mask: bool = bool(payload.get('return_mask', False))
        if not image_b64:
            return {'error': "Missing 'image' (base64)"}
        img = _b64_to_image(image_b64)
        out_rgba = _infer_rgba(img)
        if return_mask:
            alpha = out_rgba.split()[-1]
            buf = io.BytesIO()
            alpha.save(buf, format='PNG')
            mask_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            return {'mask': mask_b64}
        return {'image': _image_to_b64(out_rgba)}
    except Exception as e:
        return {'error': f'BiRef inference failed: {e}'}


if __name__ == '__main__':
    runpod.serverless.start({'handler': handler})
