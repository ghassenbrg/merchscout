#!/usr/bin/env python3
"""Example external image adapter for Merch Scout.

This is intentionally simple: it demonstrates the adapter contract and creates
an exact-size transparent PNG. Replace it with a real generator integration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    payload = json.loads(sys.stdin.read())
    width = int(payload["width"])
    height = int(payload["height"])
    output = Path(payload["outputPath"])
    concept = payload.get("concept", {})
    text = str(concept.get("visibleText") or concept.get("conceptName") or "Original Design")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center = (width // 2, height // 2)
    radius = min(width, height) // 4
    draw.ellipse(
        [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius],
        fill=(255, 255, 255, 238),
        outline=(18, 97, 128, 255),
        width=max(3, min(width, height) // 110),
    )
    font = ImageFont.load_default(size=max(14, min(width, height) // 12))
    lines = text.upper().split()[:4]
    rendered = "\n".join(lines)
    bbox = draw.multiline_textbbox((0, 0), rendered, font=font, spacing=8, align="center")
    draw.multiline_text(
        (center[0] - (bbox[2] - bbox[0]) // 2, center[1] - (bbox[3] - bbox[1]) // 2),
        rendered,
        fill=(18, 97, 128, 255),
        font=font,
        spacing=8,
        align="center",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", dpi=(300, 300))
    print(json.dumps({"adapter": "example_image_adapter", "outputPath": str(output)}))


if __name__ == "__main__":
    main()
