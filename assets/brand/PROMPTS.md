# Scrip identity prompts

## Version 2: vector design direction

Usage clarification: the S mark is the logo for branding placements. The original mint
robot is the separate mascot for the homepage and character animation. See
[robot motion provenance](motion/README.md) for the original robot's blink/look assets.

The [v2 identity](v2/README.md) is authored as SVG geometry, not generated raster artwork.
It uses a continuous S ribbon inspired by the word Scrip, forward-cut terminals to suggest
momentum, and the prior robot's two calm pill eyes as transparent cutouts. The wordmark's
initial s repeats the same ribbon. It retains mint/ink and reduces the former head/body
construction to a compact companion monogram for product, app, motion, and future 3D use.
The earlier image-generation prompts below document the v1 concept only.

The concept and 3D reference were created with the built-in image generation tool. The flat SVG symbol and custom vector wordmark were refined separately as the editable identity masters. The SVG master, rather than either raster concept, is the shape reference for future production work.

## Initial robot concept

```text
Use case: logo-brand.
Create ONE exceptional, original primary logo symbol for the brand Scrip. Scrip is a broader AI work companion: it coordinates coding agents across workspaces, keeps work flowing, improves efficiency, and helps carry a product from an idea through building and shipping. It will extend to desktop, mobile, motion identity, and a 3D mascot. The identity must represent a capable modern working robot and an ongoing product/work loop, rather than a permission or checkmark utility.

Design a minimal, compact, front-facing robot symbol built from a distinctive flowing geometric S structure. Integrate the S into the actual silhouette/visor structure, not a separate letter printed on a generic robot. Two confident, friendly, simple eye apertures. A clever continuous folded-loop feeling, a stable compact silhouette, carefully balanced negative space, precise soft corners. Very few bold shapes, readable at app-icon and favicon sizes. Professional and inventive, with personality; not childish or ornamental. The silhouette should translate naturally into an extruded 3D robot character and simple expressive motion later.

Use Scrip's existing restrained mint (#80dfbf) and deep ink (#101619) palette. Flat solid color vector-like artwork with crisp edges. Actual transparent background. The logo should occupy approximately 70 percent of the square canvas with generous equal clear space. Exactly one symbol, centered.
No wordmark, no text, no typography, no slogan. No grid or presentation board. No shadows, gradients, texture, glass, lighting, 3D rendering, glossy effects, app tile, or surrounding container. No antenna, checkmark, shield, gear, circuit lines, sparkle, rocket, infinity-orbit ornament, arms, or tools. Avoid the appearance of existing well-known robot brands. Prioritize a beautiful, ownable structural mark over decoration.
```

Saved output: `concepts/scrip-robot-concept-v1.png`.

## 3D mascot reference

Reference input: `scrip-symbol-v1.png`, exported from the flat SVG master.

```text
Use case: stylized-concept.
Asset type: Scrip 3D mascot identity reference, derived from the supplied flat logo.
The supplied image is the authoritative identity reference. Make ONE polished 3D character render of exactly this Scrip robot. Preserve its compact rounded head, swept S-fold across the helmet, two vertical pill eyes in the deep ink visor, discreet side pods, and flowing S-shaped lower body. Preserve the relative proportions, facial spacing, and mint/ink palette. Do not redesign it or put a separate letter S on it.

A calm, capable modern working companion, not a child's toy. Soft matte mint shell (#80dfbf), satin deep ink (#101619) visor/core, restrained soft studio highlights. Give the existing forms physical depth, precise smooth bevels, and believable separation of the head shell and lower ribbon body. One gentle three-quarter view, around 20 degrees turned, near-orthographic product camera. Whole character centered with generous clear space. Actual transparent background, no floor plane or surrounding scene.

No text, wordmark, captions, sheet layout, extra versions, added body/limbs, tools, antenna, mouth, eyelashes, ornaments, accessories, props, branded devices, or additional symbols. This is a future animation/3D reference; the reference image remains the canonical flat logo.
```

Saved output: `scrip-mascot-reference-v1.png`. This is a rendered concept image, not a 3D model or animation rig.
