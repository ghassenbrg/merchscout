# Design Generation Rules

Before generating artwork, create a concept brief with:

- concept name,
- niche,
- selected marketplaces,
- product fit,
- design style,
- text strategy,
- must-avoid list,
- exact visible text,
- generation prompt.

Style mapping:

- Phrase-driven niche: typography-first.
- Illustration-driven niche: original character/object composition.
- Vintage niche: retro badge, distressed texture, limited palette.
- Mug niche: horizontal wrap composition.
- T-shirt/hoodie niche: strong centered readable composition.
- Japan market: natural Japanese or no visible text.

Default production generation uses Codex `image_gen` for the raster illustration/motif, on a flat chroma-key background and with no generated text. Final text is rendered deterministically during local post-processing.

Processing rules:

- Generate imagegen source art on a flat #00ff00 chroma-key background.
- Remove chroma-key background with the system imagegen helper when the source lacks useful alpha.
- Place/crop/scale the artwork on the exact Amazon canvas.
- Render final phrase text locally with readable typography.
- Export final PNG and validate dimensions, alpha, fake background, clipping, metadata, and keywords.

Fallback/test generator:

- Must create real transparent PNG files.
- Must use exact configured canvas dimensions.
- Must not use fake checkerboard backgrounds.
- Must leave print-safe margins.
- Must write candidate options to `workspace/candidates/` and final winners to `output/final/`.
