from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def image_path_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def qimage_to_png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def qimage_to_base64(image: QImage) -> str:
    return base64.b64encode(qimage_to_png_bytes(image)).decode("ascii")


def load_pixmap(path: Path, max_width: int = 720, max_height: int = 460) -> Optional[QPixmap]:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
