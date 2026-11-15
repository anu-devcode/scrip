# Scrip / S logo

This S mark is the product logo. Use it in branding and logo placements. The original
mint robot remains the mascot for the homepage artwork and character animation. Its
animation assets live separately in [`../motion/`](../motion/README.md).

The logo is a continuous **S** ribbon with pill-shaped cutouts inspired by the original
Scrip robot. The two forward cuts give the
mark direction, while its continuous shape represents work moving from intent through
building, iteration, and shipping. It can stand for the wider product without attaching
the identity to a particular agent, IDE, model, approval button, or feature.

This is an evolution of the earlier S-loop robot: the mint and ink palette, flowing fold,
and facial signature are retained; the separate helmet, side pods, and body become one
compact silhouette. In the combined logo, the mint S symbol leads directly into custom
vector “crip” lettering. The standalone wordmark retains the full product name. No font is needed to display or reproduce the actual logo.

## Choose an asset

| File | Use |
| --- | --- |
| `scrip-symbol-v2.svg` | Mint symbol with transparent eye cutouts; master geometry |
| `scrip-wordmark-v2.svg` | Custom ink wordmark; master geometry |
| `scrip-logo-v2.svg` | Mint symbol and ink wordmark on a light surface |
| `scrip-logo-dark-v2.svg` | Mint symbol and white wordmark on an ink surface |
| `scrip-logo-ink-v2.svg` | One ink for print, engraving, and light interfaces |
| `scrip-logo-white-v2.svg` | One white for dark surfaces |
| `scrip-app-icon-v2.svg` | Ink app tile with the mint mark |
| `icons/` | App exports at 16, 24, 32, 48, 64, 128, 256, 512, and 1024 px |
| `scrip-logo-presentation-v2.png` | Ready-to-view logo on the ink background |
| `scrip-brand-board-v2.png` | Overview of the identity and its applications |
| `scrip-motion-layers-v2.svg` | Separated ribbon and eye layers on an ink composition plate |

Transparent PNGs accompany the symbols, wordmarks, and lockups. Board and presentation
images include their backgrounds. Presentation labels use Segoe UI or a sans-serif fallback;
these labels are not part of the logo.

## Use consistently

- Mint `#80DFBF`, ink `#101619`, white `#FFFFFF`; optional paper `#F4F7F3`.
- Prefer the mint/white lockup on ink, or the single-ink lockup on a light background.
- Allow at least 24 units of clear space around the visible symbol on its 256-unit grid.
- Use the full symbol at 32 px or larger when the face must be clear. At 16 px, use the
  supplied app export and treat the S silhouette as the primary recognition cue.
- Keep the eyes level and preserve the forward cuts, spacing, and aspect ratio.
- Use the flat SVGs for scalable layouts; raster exports have a fixed pixel size.
- Keep gradients, shadows, surrounding arrows, checkmarks, and vendor badges out of the logo.

## Logo layers and the separate mascot

The static master uses a compound path with true transparent cutouts. The layered source
separates `ribbon`, `eyes`, `eye-left`, and `eye-right` on `ink-plate` for editing. Use that
plate for compositing, not as the transparent logo. The S mark stays a logo; blinking,
gaze, and character motion belong to the original mint robot in `../motion/`.

Brand expression does not establish support for unshipped features or host compatibility.
This versioned design kit does not replace the artwork in already released installers.

## Regenerate

Edit the two master SVGs, then run from the repository root:

```sh
uv run --extra desktop python -m devtools.export_brand_v2
```

The exporter writes only this v2 family and `dist/brand-v2/Scrip-logo-v2-kit.zip`. It shares
SVG composition and PNG rendering with the original exporter. The v1 masters are retained.
