# Original mint robot / idle motion

The original 3D mint robot is the mascot. The v2 S mark is the product logo and belongs
in branding placements. Do not replace the robot with the S mark in homepage artwork or
other character placements.

`scrip-mascot-idle.gif` is an 8-second loop: blink, look left, look right, blink, return
to centre. The GIF has an ink background matching the homepage. The WebP version has full
alpha transparency. The PNG is the neutral still. The homepage uses the original robot
PNG when paused or when the visitor requests reduced motion.

The original `../scrip-mascot-reference-v1.png` is preserved. The animation retains its
body, head, materials, camera, and pose. The existing illuminated eyes are separated as
layers, then translated and compressed for glances and blinks. Only small visor patches
use the generated eyeless reference; the surrounding source artwork remains unchanged.
There is no finished 3D mesh or rig in this kit.

## Regenerate

```sh
uv run --extra build python -m devtools.animate_brand
```

Pillow is in the existing build extra. Timing and eye movement live in
`devtools/animate_brand.py`. The exporter writes only this motion family and an inspection
sheet under `dist/brand-v2/`.

## Image-generation provenance

`visor-clean-plate-reference.png` was prepared with the built-in image-generation tool,
using the original robot PNG as the edit target. The animation uses only its small eye
regions, then reuses the original eye pixels. Exact edit prompt:

```text
Edit target: the supplied original Scrip 3D mint robot mascot PNG. Create a precise animation clean plate of THIS EXACT image. Remove ONLY the two small glowing mint eye capsules from inside its dark visor; fill those two small eye-shaped regions with the continuation of the existing smooth dark visor surface and its subtle studio reflections. The visor must become blank, no eyes, no slits, no facial details. Preserve the exact original robot, helmet fold, head, side pods, lower S-shaped body, silhouette, proportions, three-quarter camera angle, pose, original framing, full body position, mint/ink materials, lighting, shading, shadows and reflections outside the two tiny eye regions. Do not redesign or reframe, do not change the robot's shape or surfaces. Maintain the original square canvas composition, preferably 1280 x 1280 matching the input, and actual transparent background. No additional objects, text, shadows on a floor, or scene. This is a technical clean plate for compositing the ORIGINAL eyes back as animation layers; preserving identity and registration is more important than new visual polish.
```
