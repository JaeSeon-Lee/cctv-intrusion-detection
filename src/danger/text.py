from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def put_text(
    frame: np.ndarray,
    text: str,
    org: tuple[int, int],
    font_size: int = 18,
    color: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """BGR 프레임에 한글 텍스트를 그린다. in-place."""
    font = _font(font_size)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = right - left + 4, bottom - top + 4
    x, y = org
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + tw), min(frame.shape[0], y + th)
    if x1 >= x2 or y1 >= y2:
        return frame

    crop = frame[y1:y2, x1:x2]
    image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    b, g, r = color
    draw.text((x - x1, y - y1), text, font=font, fill=(r, g, b))
    frame[y1:y2, x1:x2] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return frame
