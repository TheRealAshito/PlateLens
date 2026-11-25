"""Validação, redimensionamento e armazenamento local seguro de fotos."""

from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.config import Settings, ensure_directories

SAFE_FILENAME_RE = re.compile(r"^meal_[a-f0-9]{32}\.jpg$")


class InvalidImageError(ValueError):
    """Lançada quando o arquivo enviado não é uma imagem válida ou excede o limite."""


def process_and_save_plate_image(
    raw_bytes: bytes,
    settings: Settings,
) -> tuple[str, bytes]:
    """Valida, corrige orientação EXIF, redimensiona e salva foto como JPEG otimizado."""
    if not raw_bytes:
        raise InvalidImageError("Nenhuma imagem foi enviada.")
    if len(raw_bytes) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise InvalidImageError(f"Imagem excede o limite máximo de {max_mb} MB.")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            transposed = ImageOps.exif_transpose(img)
            if transposed.mode not in ("RGB", "L"):
                transposed = transposed.convert("RGB")
            elif transposed.mode == "L":
                transposed = transposed.convert("RGB")

            max_side = settings.max_image_side_px
            if max(transposed.size) > max_side:
                transposed.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            transposed.save(out_buf, format="JPEG", quality=84, optimize=True)
            jpeg_bytes = out_buf.getvalue()
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Formato de imagem inválido. Envie JPG, PNG ou WEBP.") from exc

    cfg = ensure_directories(settings)
    filename = f"meal_{uuid.uuid4().hex}.jpg"
    dest_path = cfg.uploads_dir / filename
    dest_path.write_bytes(jpeg_bytes)
    return filename, jpeg_bytes


def resolve_safe_upload_path(filename: str, settings: Settings) -> Path:
    """Resolve caminho de foto protegendo contra path traversal."""
    if not SAFE_FILENAME_RE.match(filename):
        raise InvalidImageError("Nome de arquivo inválido.")
    target = (settings.uploads_dir / filename).resolve()
    uploads_root = settings.uploads_dir.resolve()
    if uploads_root not in target.parents:
        raise InvalidImageError("Caminho de arquivo não permitido.")
    return target
