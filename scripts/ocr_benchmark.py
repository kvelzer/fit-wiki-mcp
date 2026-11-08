#!/usr/bin/env python3
"""Small reproducible printed CZ/EN OCR baseline; no network and no private study material."""

import io
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from fitwiki_mcp.client import Response
from fitwiki_mcp.config import Config
from fitwiki_mcp.service import Service

GOLD = "Příliš žluťoučký kůň\nČeský text a SQL dotazy.\nEnglish algebra exercise 123."


def distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def main():
    image = Image.new("RGB", (1500, 500), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    ImageDraw.Draw(image).multiline_text((50, 80), GOLD, font=font, fill="black", spacing=30)
    out = io.BytesIO()
    image.save(out, "PNG")

    class SyntheticClient:
        def get(self, url, **kwargs):
            return Response(out.getvalue(), "image/png", url)

        def close(self):
            pass

    with tempfile.TemporaryDirectory(prefix="fitwiki-ocr-") as directory:
        service = Service(Config(username="synthetic", data_dir=Path(directory)), SyntheticClient())
        try:
            result = service.attachments.read("škola:předměty:synthetic:scan.png")
            expected, actual = " ".join(GOLD.split()), " ".join(result["text"].split())
            report = {
                "sample": "synthetic-printed-cz-en",
                "method": result["method"],
                "profile": result["profile"],
                "gold_chars": len(expected),
                "gold_words": len(expected.split()),
                "cer": round(distance(expected, actual) / len(expected), 4),
                "wer": round(distance(expected.split(), actual.split()) / len(expected.split()), 4),
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            service.close()


if __name__ == "__main__":
    main()
