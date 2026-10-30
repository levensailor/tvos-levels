"""Generate the layered tvOS app icon and top-shelf artwork for Band Levels.

Run: uv run --no-project --with pillow python scripts/generate_tvos_assets.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "BandLevels" / "BandLevels" / "Assets.xcassets"
BRAND = CATALOG / "App Icon & Top Shelf Image.brandassets"
PREVIEW = ROOT / "docs" / "assets" / "top-shelf-preview.png"
FONT_PATH = ROOT / "BandLevels" / "BandLevels" / "Resources" / "Fonts" / "InterVariable.ttf"

BASE = (15, 23, 42)
BASE_DEEP = (2, 6, 23)
TEXT = (226, 232, 240)
ACCENT = (56, 189, 248)
SLOTS = 16
SLOTS_PER_ROW = 8
POPULATED = 13
LEVELS = [0.82, 0.64, 0.58, 0.9, 0.71, 0.77, 0.52, 0.95, 0.68, 0.45, 0.6, 0.55, 0.74]
XCODE_INFO = {"author": "xcode", "version": 1}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def back_layer(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), BASE)
    gradient = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        row = tuple(round(BASE[i] + (BASE_DEEP[i] - BASE[i]) * t) for i in range(3))
        gradient.line((0, y, width, y), fill=row)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    radius = int(min(width, height) * 0.55)
    cx, cy = width // 2, int(height * 0.58)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*ACCENT, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(radius * 0.6))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    return image.convert("RGB")


def panel_box(width: int, height: int, inset: float) -> tuple[int, int, int, int]:
    margin_x = int(width * inset)
    margin_y = int(height * inset * width / height * 0.6)
    return margin_x, margin_y, width - margin_x, height - margin_y


def slot_boxes(box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    left, top, right, bottom = box
    pad = int((right - left) * 0.04)
    gap = max(2, int((right - left) * 0.012))
    inner_w = right - left - 2 * pad
    inner_h = bottom - top - 2 * pad
    slot_w = (inner_w - gap * (SLOTS_PER_ROW - 1)) / SLOTS_PER_ROW
    slot_h = (inner_h - gap) / 2
    boxes = []
    for index in range(SLOTS):
        row, column = divmod(index, SLOTS_PER_ROW)
        x0 = left + pad + column * (slot_w + gap)
        y0 = top + pad + row * (slot_h + gap)
        boxes.append((round(x0), round(y0), round(x0 + slot_w), round(y0 + slot_h)))
    return boxes


def middle_layer(width: int, height: int, inset: float) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = panel_box(width, height, inset)
    radius = max(4, int(width * 0.03))
    stroke = max(1, width // 400)
    draw.rounded_rectangle(box, radius, fill=(*TEXT, 22), outline=(*TEXT, 60), width=stroke)
    for index, slot in enumerate(slot_boxes(box)):
        populated = index < POPULATED
        fill = (*TEXT, 28) if populated else (*TEXT, 8)
        outline = (*ACCENT, 70) if populated else (*TEXT, 40)
        draw.rounded_rectangle(slot, max(2, radius // 3), fill=fill, outline=outline, width=stroke)
    return image


def front_layer(width: int, height: int, inset: float) -> Image.Image:
    bars = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bars)
    for index, (x0, y0, x1, y1) in enumerate(slot_boxes(panel_box(width, height, inset))):
        if index >= POPULATED:
            continue
        slot_w, slot_h = x1 - x0, y1 - y0
        bar_w = max(2, int(slot_w * 0.34))
        bx0 = x0 + (slot_w - bar_w) // 2
        level = LEVELS[index]
        top = y1 - int(slot_h * 0.12) - int((slot_h * 0.76) * level)
        draw.rounded_rectangle(
            (bx0, top, bx0 + bar_w, y1 - int(slot_h * 0.12)), bar_w // 2, fill=(*ACCENT, 255)
        )
    glow = bars.filter(ImageFilter.GaussianBlur(max(2, width / 120)))
    return Image.alpha_composite(glow, bars)


def flattened(width: int, height: int, inset: float) -> Image.Image:
    image = back_layer(width, height).convert("RGBA")
    image = Image.alpha_composite(image, middle_layer(width, height, inset))
    return Image.alpha_composite(image, front_layer(width, height, inset))


def weighted_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        font = ImageFont.truetype(str(FONT_PATH), size)
        axes = font.get_variation_axes()
        values = [800 if "eight" in str(axis.get("name", "")) else axis["default"] for axis in axes]
        font.set_variation_by_axes(values)
        return font
    except (OSError, ValueError, KeyError):
        return ImageFont.load_default()


def top_shelf(width: int, height: int) -> Image.Image:
    image = back_layer(width, height).convert("RGBA")
    meter_width = int(width * 0.48)
    meter = Image.alpha_composite(
        middle_layer(meter_width, height, 0.06), front_layer(meter_width, height, 0.06)
    )
    image.alpha_composite(meter, (width - meter_width - int(width * 0.04), 0))
    draw = ImageDraw.Draw(image)
    title = weighted_font(int(height * 0.16))
    subtitle = weighted_font(int(height * 0.06))
    left = int(width * 0.06)
    draw.text((left, int(height * 0.32)), "BAND LEVELS", font=title, fill=(*TEXT, 255))
    draw.text(
        (left, int(height * 0.55)),
        "Gain · VU · dBFS · LUFS for every track",
        font=subtitle,
        fill=(*ACCENT, 255),
    )
    return image.convert("RGB")


def write_imagestack(name: str, sizes: dict[str, tuple[int, int]], inset: float) -> Path:
    stack = BRAND / f"{name}.imagestack"
    layers = {"Front": front_layer, "Middle": middle_layer, "Back": back_layer}
    for layer, painter in layers.items():
        imageset = stack / f"{layer}.imagestacklayer" / "Content.imageset"
        imageset.mkdir(parents=True, exist_ok=True)
        images = []
        for scale, (width, height) in sizes.items():
            filename = f"{layer.lower()}@{scale}.png"
            art = painter(width, height) if layer == "Back" else painter(width, height, inset)
            art.save(imageset / filename)
            images.append({"filename": filename, "idiom": "tv", "scale": scale})
        write_json(imageset / "Contents.json", {"images": images, "info": XCODE_INFO})
        write_json(stack / f"{layer}.imagestacklayer" / "Contents.json", {"info": XCODE_INFO})
    stack_layers = [{"filename": f"{layer}.imagestacklayer"} for layer in layers]
    write_json(stack / "Contents.json", {"info": XCODE_INFO, "layers": stack_layers})
    return stack


def write_imageset(name: str, sizes: dict[str, tuple[int, int]]) -> None:
    imageset = BRAND / f"{name}.imageset"
    imageset.mkdir(parents=True, exist_ok=True)
    images = []
    for scale, (width, height) in sizes.items():
        filename = f"{name.lower().replace(' ', '-')}@{scale}.png"
        top_shelf(width, height).save(imageset / filename)
        images.append({"filename": filename, "idiom": "tv", "scale": scale})
    write_json(imageset / "Contents.json", {"images": images, "info": XCODE_INFO})


def main() -> None:
    write_json(CATALOG / "Contents.json", {"info": XCODE_INFO})
    write_json(
        CATALOG / "AccentColor.colorset" / "Contents.json",
        {
            "colors": [
                {
                    "color": {
                        "color-space": "srgb",
                        "components": {
                            "alpha": "1.000",
                            "red": f"{ACCENT[0] / 255:.3f}",
                            "green": f"{ACCENT[1] / 255:.3f}",
                            "blue": f"{ACCENT[2] / 255:.3f}",
                        },
                    },
                    "idiom": "universal",
                }
            ],
            "info": XCODE_INFO,
        },
    )
    write_imagestack("App Icon", {"1x": (400, 240), "2x": (800, 480)}, 0.12)
    write_imagestack("App Icon - App Store", {"1x": (1280, 768), "2x": (2560, 1536)}, 0.12)
    write_imageset("Top Shelf Image", {"1x": (1920, 720), "2x": (3840, 1440)})
    write_imageset("Top Shelf Image Wide", {"1x": (2320, 720), "2x": (4640, 1440)})
    write_json(
        BRAND / "Contents.json",
        {
            "assets": [
                {
                    "filename": "App Icon - App Store.imagestack",
                    "idiom": "tv",
                    "role": "primary-app-icon",
                    "size": "1280x768",
                },
                {
                    "filename": "App Icon.imagestack",
                    "idiom": "tv",
                    "role": "primary-app-icon",
                    "size": "400x240",
                },
                {
                    "filename": "Top Shelf Image Wide.imageset",
                    "idiom": "tv",
                    "role": "top-shelf-image-wide",
                    "size": "2320x720",
                },
                {
                    "filename": "Top Shelf Image.imageset",
                    "idiom": "tv",
                    "role": "top-shelf-image",
                    "size": "1920x720",
                },
            ],
            "info": XCODE_INFO,
        },
    )
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    top_shelf(1920, 720).save(PREVIEW)
    flattened(800, 480, 0.12).save(PREVIEW.with_name("app-icon-preview.png"))
    print(f"Wrote tvOS artwork to {BRAND} and previews to {PREVIEW.parent}")


if __name__ == "__main__":
    main()
