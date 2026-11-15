"""Animate the original 3D robot mascot; the separate S logo stays static."""

from PIL import Image, ImageDraw, ImageFilter

from .export_brand import BRAND

DIRECTORY = BRAND / "motion"
DURATION = 8.0
FPS = 20
SIZE = 512
GAZE = (
    (0, 0),
    (1.6, 0),
    (2.1, -24),
    (3, -24),
    (3.45, 0),
    (3.8, 0),
    (4.3, 24),
    (5.35, 24),
    (5.8, 0),
    (8, 0),
)
BLINK = (
    (0, 1),
    (1, 1),
    (1.1, 0.08),
    (1.15, 0.08),
    (1.3, 1),
    (4.85, 1),
    (4.95, 0.08),
    (5, 0.08),
    (5.15, 1),
    (8, 1),
)
# Bounds are for the original 1254px source, entirely within its visor.
EYE_REGIONS = ((490, 420, 630, 590), (725, 438, 845, 595))


def interpolate(knots: tuple[tuple[float, float], ...], time: float) -> float:
    for (start, before), (end, after) in zip(knots[:-1], knots[1:], strict=True):
        if start <= time <= end:
            progress = (time - start) / (end - start)
            eased = progress * progress * (3 - 2 * progress)
            return before + (after - before) * eased
    return knots[-1][1]


def eye_layer(
    original: Image.Image, region: tuple[int, int, int, int]
) -> tuple[Image.Image, tuple[int, int]]:
    crop = original.crop(region)
    pixels = crop.load()
    mask = Image.new("L", crop.size)
    values = []
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, _ = pixels[x, y]
            values.append(
                round(min(1, max(0, (green - 75) / 65)) * 255)
                if green - red > 25 and green - blue > 5
                else 0
            )
    mask.putdata(values)
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError("Original mascot eye not found")
    crop.putalpha(mask)
    return crop.crop(bounds), (region[0] + bounds[0], region[1] + bounds[1])


def main() -> None:
    original = Image.open(BRAND / "scrip-mascot-reference-v1.png").convert("RGBA")
    reference = Image.open(DIRECTORY / "visor-clean-plate-reference.png").convert("RGBA")
    if original.size != (1254, 1254) or reference.size != original.size:
        raise ValueError("Animation requires the original mascot and its registered clean plate")
    eyes = [eye_layer(original, region) for region in EYE_REGIONS]
    erase = Image.new("L", original.size)
    for sprite, position in eyes:
        erase.paste(sprite.getchannel("A"), position)
    erase = erase.filter(ImageFilter.MaxFilter(35)).filter(ImageFilter.GaussianBlur(8))
    # Only eye patches use the generated clean plate. Other pixels remain original.
    plate = Image.composite(reference, original, erase)
    plate.save(DIRECTORY / "scrip-mascot-animation-plate.png")
    for index, (sprite, _) in enumerate(eyes, start=1):
        sprite.save(DIRECTORY / f"scrip-mascot-eye-{index}.png")
    frames = []
    dark_frames = []
    for index in range(round(DURATION * FPS)):
        time = index / FPS
        offset, openness = interpolate(GAZE, time), interpolate(BLINK, time)
        frame = plate.copy()
        for sprite, (x, y) in eyes:
            height = max(2, round(sprite.height * openness))
            eye = sprite.resize((sprite.width, height), Image.Resampling.LANCZOS)
            frame.alpha_composite(eye, (round(x + offset), round(y + (sprite.height - height) / 2)))
        frame = frame.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
        frames.append(frame)
        dark = Image.new("RGBA", frame.size, "#101619")
        dark.alpha_composite(frame)
        dark_frames.append(dark.convert("RGB"))
    palette = dark_frames[0].quantize(colors=256)
    gif_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in dark_frames
    ]
    gif = DIRECTORY / "scrip-mascot-idle.gif"
    gif_frames[0].save(
        gif,
        save_all=True,
        append_images=gif_frames[1:],
        duration=round(1000 / FPS),
        loop=0,
        optimize=True,
        disposal=1,
    )
    frames[0].save(
        DIRECTORY / "scrip-mascot-idle.webp",
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0,
        lossless=True,
        method=6,
    )
    frames[0].save(DIRECTORY / "scrip-mascot-idle.png")
    atlas = Image.new("RGB", (768, 576), "#101619")
    draw = ImageDraw.Draw(atlas)
    with Image.open(gif) as playback:
        for slot, (label, target) in enumerate(
            (
                ("Original robot", 0),
                ("Blink", 1100),
                ("Look left", 2500),
                ("Look right", 4600),
                ("Blink right", 4950),
                ("Return", 6500),
            )
        ):
            elapsed = 0
            playback.seek(0)
            while elapsed + playback.info.get("duration", 50) <= target:
                elapsed += playback.info.get("duration", 50)
                playback.seek(playback.tell() + 1)
            x, y = slot % 3 * 256, slot // 3 * 288
            atlas.paste(
                playback.convert("RGB").resize((256, 256), Image.Resampling.LANCZOS), (x, y)
            )
            draw.text((x + 24, y + 260), label, fill="#BFD0C7")
    output = BRAND.parents[1] / "dist/brand-v2"
    output.mkdir(parents=True, exist_ok=True)
    atlas.save(output / "robot-motion-frames.png")
    print(f"Exported original robot GIF and transparent WebP ({DURATION:g}s loop).")


if __name__ == "__main__":
    main()
