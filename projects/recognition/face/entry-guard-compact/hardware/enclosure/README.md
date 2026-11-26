# Enclosure and product 3D model

GitHub shows `.stl` files as an interactive 3D viewer (click a file, drag to rotate). Open these:

| File | What |
|---|---|
| [`solavis-camera-assembled.stl`](solavis-camera-assembled.stl) | **The whole product assembled**: shell, solar panel with cells, glass, lens stack, PIR dome, LED, gold-sun inlay, board, battery, back plate (125 × 107 × 80 mm with hood) |
| [`solavis-camera-exploded.stl`](solavis-camera-exploded.stl) | The same product pulled apart so every internal part is visible |
| [`cover.stl`](cover.stl), [`backplate.stl`](backplate.stl), [`lens_hood.stl`](lens_hood.stl) | The three printable parts (print orientation) |
| `solavis-camera.glb`, `solavis-camera.manifest.json` | Same model with colours and named parts, for the portfolio's interactive viewer |

GitHub's preview is single-colour. The coloured, interactive version is on the portfolio page.

Rebuild everything from code (one parameter block drives both the print model and the presentation model):
```bash
pip install manifold3d trimesh numpy scipy networkx
python build_enclosure.py          # the three print parts
python build_product_model.py      # glb + manifest + the two product STL files
```
Status: design. Not printed, not assembled. Internal part shapes are simplified; real board, panel and cell-holder dimensions are still to be confirmed.
