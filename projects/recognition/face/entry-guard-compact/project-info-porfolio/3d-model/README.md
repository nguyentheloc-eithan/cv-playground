# Solavis camera 3D model

| File | What |
|---|---|
| `solavis-camera.glb` | One glTF binary, 26 named meshes with PBR materials, units cm, Y up, front faces +Z, about 700 KB, 26,840 triangles |
| `solavis-camera.manifest.json` | Part names, groups (shell, optics, sensors, solar, electronics, power), triangle counts, exploded-view offsets in cm (x right, y up, z toward the front) |
| `build_product_model.py` | Generator (python 3, `pip install manifold3d trimesh numpy scipy networkx`). `python build_product_model.py <out_dir>`. Same parameters as the print model `hardware/enclosure/build_enclosure.py` |

Load in Next.js with `@react-three/drei` `useGLTF('/models/solavis-camera.glb')`. Find parts with `scene.getObjectByName('pcb')` etc. Move parts by the manifest offsets for the exploded view. Materials are named (`shell_white`, `plate_graphite`, `glass_dark`, `solar_cell`, `led_warm`, `badge_gold`, ...) so finish changes and highlights are one lookup. The glass material is replaced by a physical clear-coat material in the viewer.

Status: design render. Internal parts are simplified; dimensions of the real board, panel and holder are still to be confirmed (see hardware spec). Not printed, not assembled.
