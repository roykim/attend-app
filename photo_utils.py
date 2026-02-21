# -*- coding: utf-8 -*-
"""사진 리사이즈·base64 인코딩 (시트 저장용)."""

import base64
import io

from PIL import Image

from config import PHOTO_B64_MAX, PHOTO_HEIGHT, PHOTO_WIDTH


def resize_photo_to_final(pil_img: "Image.Image") -> bytes:
    """PIL 이미지를 고정 크기(3:4)로 리사이즈해 JPEG bytes 반환."""
    if pil_img is None:
        return b""
    try:
        if pil_img.mode in ("RGBA", "P"):
            pil_img = pil_img.convert("RGB")
        img = pil_img.resize((PHOTO_WIDTH, PHOTO_HEIGHT), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return b""


def image_to_base64_for_sheet(image_bytes: bytes, mime_type: str) -> str:
    """이미지를 리사이즈·압축해 시트 한 셀에 들어가는 base64 문자열로 반환."""
    if not image_bytes:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        out = io.BytesIO()
        max_side = 320
        quality = 72
        for _ in range(6):
            w, h = img.size
            if max(w, h) > max_side:
                ratio = max_side / max(w, h)
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            img.save(out, format="JPEG", quality=quality, optimize=True)
            b64 = base64.b64encode(out.getvalue()).decode("ascii")
            if len(b64) <= PHOTO_B64_MAX:
                return b64
            out.seek(0)
            out.truncate(0)
            max_side = int(max_side * 0.8)
            quality = max(50, quality - 8)
        b64 = base64.b64encode(out.getvalue()).decode("ascii")
        return b64[:PHOTO_B64_MAX] if len(b64) > PHOTO_B64_MAX else b64
    except Exception:
        return ""
