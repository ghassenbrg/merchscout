# Amazon Product Dimensions

Merch Scout uses `assets/product-canvas-presets.json` as the local canvas source of truth for v1.

Initial presets:

| Canvas | Dimensions | Background |
| --- | ---: | --- |
| `standard_apparel` | 4500 x 5400 | transparent PNG |
| `cropped_apparel_front_hoodie` | 4500 x 4050 | transparent PNG |
| `performance_square` | 1200 x 1200 | transparent PNG |
| `hats` | 1500 x 675 | transparent PNG |
| `popsockets` | 485 x 485 | transparent PNG |
| `phone_cases` | 1800 x 3200 | full bleed |
| `tote_pillow` | 2925 x 2925 | transparent PNG |
| `tumblers_bottles` | 3000 x 1400 | transparent PNG |
| `mugs` | 2700 x 1050 | transparent PNG |

Validators must inspect actual image pixels and metadata:

- PNG format.
- Exact width and height.
- Alpha channel when required.
- Real transparent pixels, not fake checkerboard.
- No accidental solid background.
- No obvious clipping at edges.
- Reasonable file size, default max 25 MB.
- 300 DPI metadata where possible.
- sRGB if available; warn when unknown.

Before production use, compare these presets with the current official Amazon Merch on Demand template page and the user's account UI.
