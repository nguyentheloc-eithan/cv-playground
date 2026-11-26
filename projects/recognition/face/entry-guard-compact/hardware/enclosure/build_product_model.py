"""Presentation model of the Solavis gate camera: every part is a named mesh with a PBR material, exported as one GLB.

Run:  python build_product_model.py [out_dir]
Needs: pip install manifold3d numpy trimesh
Writes: solavis-camera.glb and solavis-camera.manifest.json (part names, groups, exploded-view offsets).

Same dimensions as build_enclosure.py (the print model). This file adds what a print file does not need:
rounded product shell, solar cells, glass, lens stack, PIR dome, LED, inlay badge and the internal parts.
Frame while building: x left/right, y out from the wall (front is y = D), z up. Export maps it to glTF (x mirrored, y up, front = +z), units cm.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold

# ---------------- PARAMETERS (keep in step with build_enclosure.py) ----------------
W, D, HF, TILT = 125.0, 90.0, 55.0, 15.0
T, T_TOP, PL, CLR = 3.5, 6.5, 5.0, 0.4
R_OUT = 5.0                                  # outer rounding of the shell
PANEL_W, PANEL_L = 110.0, 80.0
CAM_X, CAM_Z = W / 2, 27.0
PIR_X, LED_X = W / 2 - 40, W / 2 + 40
SEG = 64
a = math.radians(TILT)
HB = HF + D * math.tan(a)


def top_in(y):
    return HB - y * math.tan(a) - T_TOP / math.cos(a)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cyl_y(x, z, y0, y1, d, d2=None):
    c = Manifold.cylinder(y1 - y0, d / 2, (d2 if d2 is not None else d) / 2, SEG).rotate((-90, 0, 0))
    return c.translate((x, y0, z))


def cyl_x(y, z, x0, x1, d):
    return Manifold.cylinder(x1 - x0, d / 2, d / 2, SEG).rotate((0, 90, 0)).translate((x0, y, z))


def cyl_z(x, y, z0, z1, d):
    return Manifold.cylinder(z1 - z0, d / 2, d / 2, SEG).translate((x, y, z0))


def ball(x, y, z, r, sy=1.0):
    return Manifold.sphere(r, SEG).scale((1, sy, 1)).translate((x, y, z))


def rounded_wedge(y0, y1, x0, x1, r, top_inset=0.0):
    """Hull of spheres: the wedge profile (flat bottom, sloped top) with every edge rounded by r."""
    pts = []
    for x in (x0 + r, x1 - r):
        for y in (y0 + r, y1 - r):
            top = HB - y * math.tan(a) - top_inset / math.cos(a) - r / math.cos(a)
            for z in (r, top):
                pts.append(ball(x, y, z, r))
    return Manifold.batch_hull(pts)


# ---------------- SHELL ----------------
outer = rounded_wedge(-PL, D, 0, W, R_OUT)
cavity = rounded_wedge(-2.0, D - T, T, W - T, 1.5, top_inset=T_TOP)
cover = (outer ^ box(-1, W + 1, 0, D + 1, -1, HB + 20)) - cavity
plate = outer ^ box(-1, W + 1, -PL - 1, 0, -1, HB + 20)

# solar panel pocket (same maths as the print model)
u = np.array([math.cos(a), -math.sin(a)])
s0 = (D / math.cos(a) - PANEL_L) / 2
y0, z0 = s0 * u[0], HB + s0 * u[1]


def on_panel(m):
    return m.rotate((-TILT, 0, 0)).translate((W / 2, y0, z0))


cover = cover - on_panel(Manifold.cube((PANEL_W, PANEL_L, 10)).translate((-PANEL_W / 2, 0, -3.2)))
cover = cover - cyl_z(W - 22, 12, HB - 60, HB + 5, 6.5)

# front openings
cover = cover - cyl_y(CAM_X, CAM_Z, D - T - 1, D + 1, 16.0) - cyl_y(CAM_X, CAM_Z, D - 1.6, D + 1, 20.4)
cover = cover - cyl_y(PIR_X, CAM_Z, D - T - 1, D + 1, 12.0) - cyl_y(LED_X, CAM_Z, D - T - 1, D + 1, 8.2)
# board posts, battery cradle, vent, screw holes
PCB_PATTERN = (50.0, 28.0)
for dx in (-PCB_PATTERN[0] / 2, PCB_PATTERN[0] / 2):
    for dz in (-PCB_PATTERN[1] / 2, PCB_PATTERN[1] / 2):
        cover = cover + cyl_y(CAM_X + dx, CAM_Z + dz, D - T - 8, D - T + 0.5, 7.0) - cyl_y(CAM_X + dx, CAM_Z + dz, D - T - 7, D - T - 1, 2.2)
bx, by, cx, cy = 40.0, 11.0, W / 2, 42.0
cover = cover + box(cx - bx - 2, cx + bx + 2, cy - by - 2, cy + by + 2, T - 0.1, T + 6) - box(cx - bx, cx + bx, cy - by, cy + by, T - 1, T + 7)
cover = cover - cyl_z(W / 2, 72, -1, T + 1, 12.2)
SCREW_X = (18.0, W / 2, W - 18.0)
for sx in SCREW_X:
    cover = cover - cyl_z(sx, 8, -1, T + 1, 3.4)

# back plate: tongue ring, screw shelves, hidden wall-screw holes
xt0, xt1, zt0, zt1 = T + CLR, W - T - CLR, T + CLR, top_in(8) - CLR
plate = plate + box(xt0, xt1, 0, 8, zt0, zt1) - box(xt0 + 3, xt1 - 3, -1, 9, zt0 + 3, zt1 - 3)
for sx in SCREW_X:
    plate = plate + box(sx - 7, sx + 7, 0, 16, T + 0.3, T + 10.3) - cyl_z(sx, 8, T, T + 11, 3.2)
for hx in (32.0, W - 32.0):
    for hz in (24.0, 50.0):
        plate = plate - cyl_y(hx, hz, -PL - 1, 1, 5.5) - cyl_y(hx, hz, -PL - 1, -PL + 3, 10.5)

# ---------------- EXTERNAL PARTS ----------------
hood = cyl_y(CAM_X, CAM_Z, D, D + 12, 28.0, 25.0) - cyl_y(CAM_X, CAM_Z, D - 1, D + 13, 20.8)
hood = hood - cyl_y(CAM_X, CAM_Z, D + 11.2, D + 13, 24.0, 24.0) + cyl_y(CAM_X, CAM_Z, D + 11.4, D + 12, 23.4, 23.4) - cyl_y(CAM_X, CAM_Z, D + 10, D + 13, 20.8)

glass = cyl_y(CAM_X, CAM_Z, D - 1.6, D - 0.1, 20.0)
lens_ring_1 = cyl_y(CAM_X, CAM_Z, D - T - 0.4, D - 2.0, 14.0) - cyl_y(CAM_X, CAM_Z, D - T - 1, D - 1.0, 11.2)
lens_ring_2 = cyl_y(CAM_X, CAM_Z, D - T - 0.4, D - 2.6, 11.2) - cyl_y(CAM_X, CAM_Z, D - T - 1, D - 1.0, 8.6)
lens_glass = ball(CAM_X, D - 3.2, CAM_Z, 4.3, 0.42)
lens_coat = cyl_y(CAM_X, CAM_Z, D - 3.1, D - 2.9, 8.2) - cyl_y(CAM_X, CAM_Z, D - 3.2, D - 2.8, 5.6)

pir = ball(PIR_X, D - 1.2, CAM_Z, 5.7, 0.6) ^ box(PIR_X - 7, PIR_X + 7, D - T, D + 6, CAM_Z - 7, CAM_Z + 7)
for rr in (1.6, 2.7, 3.8, 4.9):
    pir = pir - (cyl_y(PIR_X, CAM_Z, D - 3, D + 6, rr * 2 + 0.34) - cyl_y(PIR_X, CAM_Z, D - 4, D + 7, rr * 2 - 0.34)) ^ box(PIR_X - 7, PIR_X + 7, D - 0.2, D + 6, CAM_Z - 7, CAM_Z + 7)

led_bezel = cyl_y(LED_X, CAM_Z, D - 1.2, D + 0.5, 8.2) - cyl_y(LED_X, CAM_Z, D - 2, D + 1, 6.4)
led_lens = ball(LED_X, D - 1.0, CAM_Z, 3.1, 0.55)

BZ = 43.0                                    # badge: a small gold sun inlay above the lens
badge = cyl_y(CAM_X, BZ, D - 0.2, D + 0.45, 4.6)
for k in range(8):
    ang = k * 45
    ray = box(-0.35, 0.35, D - 0.2, D + 0.45, 3.0, 5.0).rotate((0, ang, 0)).translate((CAM_X, 0, BZ))
    badge = badge + ray
cover = cover - cyl_y(CAM_X, BZ, D - 0.6, D + 1, 4.9)        # shallow seat, badge sits in it
for k in range(8):
    cover = cover - box(-0.4, 0.4, D - 0.6, D + 1, 2.95, 5.05).rotate((0, k * 45, 0)).translate((CAM_X, 0, BZ))

vent_plug = cyl_z(W / 2, 72, -0.8, 1.2, 14.0) - cyl_z(W / 2, 72, -1, 0.2, 9)
vent_plug = vent_plug + cyl_z(W / 2, 72, 1.2, T + 1.5, 11.8)

# solar panel (frame, cells, busbars) in the cover's pocket frame
panel_frame = on_panel(box(-PANEL_W / 2 + 0.2, PANEL_W / 2 - 0.2, 0.2, PANEL_L - 0.2, -3.0, -0.9))
cells, bus = [], []
NC, NR, G, M = 5, 3, 1.2, 3.0
cw = (PANEL_W - 2 * M - (NC - 1) * G) / NC
ch = (PANEL_L - 2 * M - (NR - 1) * G) / NR
for i in range(NC):
    for j in range(NR):
        cx0 = -PANEL_W / 2 + M + i * (cw + G)
        cy0 = M + j * (ch + G)
        cells.append(box(cx0, cx0 + cw, cy0, cy0 + ch, -0.9, -0.45))
        for f in (0.33, 0.66):
            bus.append(box(cx0 + cw * f - 0.17, cx0 + cw * f + 0.17, cy0, cy0 + ch, -0.45, -0.38))
panel_cells = on_panel(Manifold.batch_boolean(cells, 0))      # 0 = union
panel_bus = on_panel(Manifold.batch_boolean(bus, 0))

# ---------------- INTERNAL PARTS (for the exploded view) ----------------
PY = D - T - 8                               # front face of the board stack (top of the posts)
pcb = box(CAM_X - 31, CAM_X + 31, PY - 1.6, PY, CAM_Z - 20, CAM_Z + 20)
for dx in (-25, 25):
    for dz in (-14, 14):
        pcb = pcb - cyl_y(CAM_X + dx, CAM_Z + dz, PY - 2, PY + 1, 2.7)
esp = box(CAM_X - 20, CAM_X - 2, PY - 5.2, PY - 1.6, CAM_Z - 4, CAM_Z + 12)
lte = box(CAM_X + 2, CAM_X + 24, PY - 4.6, PY - 1.6, CAM_Z - 14, CAM_Z + 6)
chips = Manifold.batch_boolean([
    box(CAM_X - 28, CAM_X - 23, PY - 3.0, PY - 1.6, CAM_Z - 16, CAM_Z - 10),
    box(CAM_X - 28, CAM_X - 24, PY - 2.6, PY - 1.6, CAM_Z - 6, CAM_Z - 2),
    box(CAM_X + 6, CAM_X + 12, PY - 3.2, PY - 1.6, CAM_Z - 18, CAM_Z - 15),
    box(CAM_X + 14, CAM_X + 28, PY - 3.4, PY - 1.6, CAM_Z + 10, CAM_Z + 16),
    box(CAM_X - 8, CAM_X + 2, PY - 2.4, PY - 1.6, CAM_Z - 18, CAM_Z - 13),
], 0)
cam_mod = box(CAM_X - 6.5, CAM_X + 6.5, PY, PY + 1.2, CAM_Z - 6.5, CAM_Z + 6.5) + cyl_y(CAM_X, CAM_Z, PY + 1.2, D - T - 0.5, 8.0)
battery = cyl_x(cy, 12.5, cx - 33, cx + 33, 18.0)
batt_caps = cyl_x(cy, 12.5, cx - 34, cx - 32.5, 17.0) + cyl_x(cy, 12.5, cx + 32.5, cx + 34, 17.0) + cyl_x(cy, 12.5, cx + 34, cx + 35, 7.0)
antenna = box(8, 48, 18, 19.0, 12, 20)
magnet = cyl_y(W - 25, HB - 17, -0.4, 3.0, 6.0)
reed = cyl_x(10, top_in(10) - 7, W - 32, W - 18, 2.6)
hood_ring = None

# ---------------- MATERIALS ----------------
def mat(name, rgb, metal=0.0, rough=0.6, emissive=None, alpha=1.0):
    return trimesh.visual.material.PBRMaterial(
        name=name, baseColorFactor=[*rgb, alpha], metallicFactor=metal, roughnessFactor=rough,
        emissiveFactor=emissive or [0, 0, 0], alphaMode="BLEND" if alpha < 1 else "OPAQUE")


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


PARTS = [
    # name, manifold, material, group
    ("cover", cover, mat("shell_white", rgb("#ECE9E2"), 0.0, 0.52), "shell"),
    ("backplate", plate, mat("plate_graphite", rgb("#2A2E35"), 0.1, 0.55), "shell"),
    ("hood", hood, mat("hood_black", rgb("#14161A"), 0.1, 0.7), "optics"),
    ("glass", glass, mat("glass_dark", rgb("#0B0D12"), 0.0, 0.04, alpha=0.55), "optics"),
    ("lens_ring_1", lens_ring_1, mat("lens_metal", rgb("#3B4048"), 0.9, 0.3), "optics"),
    ("lens_ring_2", lens_ring_2, mat("lens_black", rgb("#0E1014"), 0.2, 0.5), "optics"),
    ("lens_glass", lens_glass, mat("lens_coat_blue", rgb("#1B1C5A"), 0.7, 0.08, emissive=[0.03, 0.04, 0.2]), "optics"),
    ("lens_coat", lens_coat, mat("lens_coat_gold", rgb("#C9A227"), 0.8, 0.2, emissive=[0.12, 0.09, 0.0]), "optics"),
    ("pir_dome", pir, mat("pir_frost", rgb("#F4F1EA"), 0.0, 0.35, alpha=0.92), "sensors"),
    ("led_bezel", led_bezel, mat("bezel_steel", rgb("#9AA1AB"), 1.0, 0.25), "sensors"),
    ("led_lens", led_lens, mat("led_warm", rgb("#FFF1C9"), 0.0, 0.25, emissive=[1.0, 0.86, 0.5]), "sensors"),
    ("badge", badge, mat("badge_gold", rgb("#D4A017"), 1.0, 0.22), "shell"),
    ("vent_plug", vent_plug, mat("rubber_black", rgb("#16181C"), 0.0, 0.8), "shell"),
    ("panel_frame", panel_frame, mat("alu_frame", rgb("#8D949E"), 0.9, 0.35), "solar"),
    ("panel_cells", panel_cells, mat("solar_cell", rgb("#0E1B3D"), 0.6, 0.18), "solar"),
    ("panel_busbars", panel_bus, mat("busbar_silver", rgb("#C7CDD6"), 1.0, 0.3), "solar"),
    ("pcb", pcb, mat("pcb_green", rgb("#0F5D4E"), 0.1, 0.5), "electronics"),
    ("esp32", esp, mat("shield_steel", rgb("#B5BBC4"), 1.0, 0.28), "electronics"),
    ("lte_module", lte, mat("lte_black", rgb("#1A1D22"), 0.2, 0.45), "electronics"),
    ("chips", chips, mat("ic_black", rgb("#0D0F12"), 0.1, 0.5), "electronics"),
    ("camera_module", cam_mod, mat("cam_black", rgb("#16181D"), 0.3, 0.4), "electronics"),
    ("battery", battery, mat("cell_wrap", rgb("#1F5FD0"), 0.1, 0.4), "power"),
    ("battery_caps", batt_caps, mat("cell_steel", rgb("#CBD1D9"), 1.0, 0.25), "power"),
    ("antenna", antenna, mat("fpc_gold", rgb("#C8962B"), 0.8, 0.35), "electronics"),
    ("magnet", magnet, mat("magnet_nickel", rgb("#B0B7C0"), 1.0, 0.3), "sensors"),
    ("reed", reed, mat("reed_glass", rgb("#9FD6C9"), 0.0, 0.1, alpha=0.7), "sensors"),
]

# Exploded view offsets in mm along glTF axes (x right, y up, z toward the viewer at the front)
EXPLODE = {
    "hood": [0, 0, 46], "glass": [0, 0, 30], "lens_ring_1": [0, 0, 18], "lens_ring_2": [0, 0, 12], "lens_glass": [0, 0, 6],
    "lens_coat": [0, 0, 9], "pir_dome": [0, 0, 24], "led_bezel": [0, 0, 22], "led_lens": [0, 0, 32], "badge": [0, 0, 14],
    "panel_frame": [0, 46, 0], "panel_cells": [0, 56, 0], "panel_busbars": [0, 60, 0],
    "camera_module": [0, 0, -14], "pcb": [0, 0, -30], "esp32": [0, 0, -42], "lte_module": [0, 0, -42], "chips": [0, 0, -40],
    "battery": [0, -26, -30], "battery_caps": [0, -26, -30], "antenna": [-30, 0, -30],
    "reed": [0, 12, -56], "magnet": [0, 12, -64], "backplate": [0, 0, -84], "vent_plug": [0, -26, 0],
}


def to_gl(tm):
    v = np.asarray(tm.vertices, float)
    g = np.column_stack([-(v[:, 0] - W / 2), v[:, 2], v[:, 1]]) * 0.1      # mm -> cm
    return trimesh.Trimesh(g, tm.faces, process=False)


def as_mesh(m):
    mm = m.to_mesh()
    t = trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=True)
    t = to_gl(t)
    t.merge_vertices()
    return trimesh.graph.smooth_shade(t, angle=np.radians(38))


out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
scene = trimesh.Scene()
info = []
for name, m, material, group in PARTS:
    if m.is_empty():
        raise SystemExit(f"{name} is empty")
    t = as_mesh(m)
    t.visual = trimesh.visual.TextureVisuals(material=material)
    scene.add_geometry(t, node_name=name, geom_name=name)
    info.append({"name": name, "group": group, "material": material.name, "triangles": int(len(t.faces)),
                 "explode_cm": [round(c / 10, 2) for c in EXPLODE.get(name, [0, 0, 0])]})
out.mkdir(parents=True, exist_ok=True)
glb = out / "solavis-camera.glb"
glb.write_bytes(scene.export(file_type="glb"))
(out / "solavis-camera.manifest.json").write_text(json.dumps({
    "units": "cm", "size_mm": [W, round(HB, 1), D + PL], "tilt_deg": TILT,
    "note": "Presentation model. Design only, not yet printed or assembled.",
    "parts": info}, indent=2))
print(f"{glb}  {glb.stat().st_size / 1024:.0f} KB, {sum(p['triangles'] for p in info)} triangles, {len(info)} parts")
print("bounds cm:", np.round(scene.bounds, 2).tolist())
