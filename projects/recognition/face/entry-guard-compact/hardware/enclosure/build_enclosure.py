"""Parametric compact one-box enclosure for the solar gate camera (Rev B, off-the-shelf parts).

Run:  python build_enclosure.py      -> writes cover.stl, backplate.stl and lens_hood.stl next to this file.
Needs: pip install manifold3d numpy trimesh

World frame: x = left/right, y = out from the wall (front is y = D), z = up.
All sizes in mm. Change the numbers in the PARAMETERS block, then rebuild.
"""
import math
from pathlib import Path
import numpy as np
import trimesh
from manifold3d import Manifold, CrossSection

# ---------------- PARAMETERS ----------------
W = 125.0        # outer width
D = 90.0         # depth, wall to front face
HF = 55.0        # outer height at the front face
TILT = 15.0      # panel tilt in degrees (top slopes down toward the front)
T = 3.5          # wall thickness
T_TOP = 6.5      # top wall thickness (includes the 3.2 mm panel pocket)
PANEL_W, PANEL_L, PANEL_DEPTH = 110.0, 80.0, 3.2    # 6 V ~1.5 W panel, CONFIRM against the real panel
BAT = (80.0, 22.0)           # single 18650 holder footprint (x, y), CONFIRM against the real holder
CLR = 0.4        # fit clearance
CAM_X, CAM_Z = W / 2, 27.0
PIR_X, LED_X = W / 2 - 40, W / 2 + 40
PCB_PATTERN = (50.0, 28.0)   # PLACEHOLDER mounting-hole pitch (x, z) of the dev board, set it from the real board
# --------------------------------------------

a = math.radians(TILT)
HB = HF + D * math.tan(a)                     # outer height at the wall
def top_in(y):                                # inner ceiling height at depth y
    return HB - y * math.tan(a) - T_TOP / math.cos(a)

def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))

def cyl_y(x, z, y0, y1, d):                   # cylinder along +y
    c = Manifold.cylinder(y1 - y0, d / 2, d / 2, 48).rotate((-90, 0, 0))
    return c.translate((x, y0, z))

def cyl_z(x, y, z0, z1, d):                   # cylinder along +z
    return Manifold.cylinder(z1 - z0, d / 2, d / 2, 48).translate((x, y, z0))

def extrude_yz(poly, x0, x1):                 # polygon given in (y, z), extruded along x
    m = Manifold.extrude(CrossSection([poly]), x1 - x0)
    perm = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
    return m.transform(perm).translate((x0, 0, 0))

# ---------------- COVER ----------------
outer = extrude_yz([(0, 0), (D, 0), (D, HF), (0, HB)], 0, W)
cavity = extrude_yz([(-1, T), (D - T, T), (D - T, top_in(D - T)), (-1, top_in(-1))], T, W - T)
cover = outer - cavity

# panel pocket in the sloped top
u = np.array([math.cos(a), -math.sin(a)])      # (y, z) direction down the slope
slope_len = D / math.cos(a)
s0 = (slope_len - PANEL_L) / 2
y0, z0 = s0 * u[0], HB + s0 * u[1]
pocket = Manifold.cube((PANEL_W, PANEL_L, 10)).translate((-PANEL_W / 2, 0, -PANEL_DEPTH))
pocket = pocket.rotate((-TILT, 0, 0)).translate((W / 2, y0, z0))
cover = cover - pocket
# panel cable hole (vertical) inside the pocket, near the high edge
cover = cover - cyl_z(W - 22, 12, HB - 60, HB + 5, 6.5)

# front-face openings (all through the front wall)
yf0, yf1 = D - T - 1, D + 1
cover = cover - cyl_y(CAM_X, CAM_Z, yf0, yf1, 16.0)          # camera view
cover = cover - cyl_y(CAM_X, CAM_Z, D - 1.6, yf1, 20.4)      # window recess (20 mm glass or acrylic disc)
cover = cover - cyl_y(PIR_X, CAM_Z, yf0, yf1, 12.0)          # PIR dome
cover = cover - cyl_y(LED_X, CAM_Z, yf0, yf1, 8.2)           # white LED
# lens hood is a separate part (see HOOD below), glued around the window recess

# PCB standoffs on the inside of the front wall (M2.5 self-tapping)
for dx in (-PCB_PATTERN[0] / 2, PCB_PATTERN[0] / 2):
    for dz in (-PCB_PATTERN[1] / 2, PCB_PATTERN[1] / 2):
        post = cyl_y(CAM_X + dx, CAM_Z + dz, D - T - 8, D - T + 0.5, 7.0)
        cover = cover + post - cyl_y(CAM_X + dx, CAM_Z + dz, D - T - 7, D - T - 1, 2.2)

# battery cradle (2 x 18650 holder, about 78 x 40 mm) on the floor
cx, cy = W / 2, 42.0
bx, by = BAT[0] / 2, BAT[1] / 2
ring = box(cx - bx - 2, cx + bx + 2, cy - by - 2, cy + by + 2, T - 0.1, T + 6) - box(cx - bx, cx + bx, cy - by, cy + by, T - 1, T + 7)
cover = cover + ring

# breather vent hole (M12 vent plug, optional) and 3 screw holes in the floor
cover = cover - cyl_z(W / 2, 72, -1, T + 1, 12.2)
SCREW_X = (18.0, W / 2, W - 18.0)
for sx in SCREW_X:
    cover = cover - cyl_z(sx, 8, -1, T + 1, 3.4)

# ---------------- BACK PLATE ----------------
PL = 5.0
plate = box(0, W, -PL, 0, 0, HB)
xt0, xt1 = T + CLR, W - T - CLR
zt0, zt1 = T + CLR, top_in(8) - CLR
ring_t = box(xt0, xt1, 0, 8, zt0, zt1) - box(xt0 + 3, xt1 - 3, -1, 9, zt0 + 3, zt1 - 3)
plate = plate + ring_t
for sx in SCREW_X:                              # screw shelves for the cover screws
    shelf = box(sx - 7, sx + 7, 0, 16, T + 0.3, T + 10.3)
    shelf = shelf - cyl_z(sx, 8, T, T + 11, 3.2) - cyl_z(sx, 8, T + 4.6, T + 11, 4.2)
    plate = plate + shelf
for hx in (32.0, W - 32.0):                     # hidden wall-screw holes, reached once the cover is off
    for hz in (24.0, 50.0):
        plate = plate - cyl_y(hx, hz, -PL - 1, 1, 5.5) - cyl_y(hx, hz, -3, 1, 10.5)

# ---------------- LENS HOOD (separate part, glued to the front face) ----------------
HOOD = cyl_z(0, 0, 0, 12, 28.0) - cyl_z(0, 0, -1, 13, 20.8)

# ---------------- CHECK AND EXPORT ----------------
def stl(m, path):
    mesh = m.to_mesh()
    t = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
    t.export(path)
    return t

here = Path(__file__).parent
# print orientation: cover front-face down, plate back-face down
cover_print = cover.rotate((-90, 0, 0)).translate((0, 0, D))
plate_print = plate.rotate((90, 0, 0)).translate((0, HB, PL))
tc = stl(cover_print, here / "cover.stl")
tp = stl(plate_print, here / "backplate.stl")
th = stl(HOOD, here / "lens_hood.stl")
overlap = (cover ^ plate).volume()
print(f"cover     : {tc.bounds[1] - tc.bounds[0]} mm, {tc.volume/1000:.1f} cm3, watertight={tc.is_watertight}")
print(f"backplate : {tp.bounds[1] - tp.bounds[0]} mm, {tp.volume/1000:.1f} cm3, watertight={tp.is_watertight}")
print(f"lens hood : {th.bounds[1] - th.bounds[0]} mm, {th.volume/1000:.1f} cm3, watertight={th.is_watertight}")
print(f"cover/plate overlap volume: {overlap:.2f} mm3 (should be about 0)")
print(f"outer size W x D x H(back) = {W:.0f} x {D:.0f} x {HB:.0f} mm")
