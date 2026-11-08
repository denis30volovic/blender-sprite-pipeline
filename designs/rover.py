"""Rover: a six-wheeled scout car with a gun turret (worked vehicle example).

Two sprites, the usual split for vehicle frameworks:
- the hull in the oblique view, one texture per facing (the game mirrors east for west), centred on the
  footprint centre so no per-facing draw offset is needed; the turret ring is hull art;
- the turret straight top-down, pointing north, centred on its pivot, so the game can turn it freely.
`pivot` is the turret's pivot in the hull frame; the review sheet draws the turret there in every facing, and
common.oblique_offset() gives the per-facing offset to put in the vehicle's turret draw settings.

Model space: cells, ground z = 0, front = -Y, +X = the vehicle's left. One body, not boxes on a tray: the
hull is one hull() with a sloped glacis and sides; parts are tucked into it, never floating.
"""
from spritekit.kit import Sprite, box, cyl, hull, mx

L, W = 1.42, 0.62          # half length, half width of the body at the waist
PIVOT = (0.0, 0.28, 0.86)
DYE = (164, 150, 112)


def glacis(s, x):
    """Point on the sloped front plate: s = 0 at the nose top, 1 where it meets the roof."""
    return (x, -1.40 + 0.86 * s, 0.50 + 0.36 * s)


def hull_art(ctx):
    # wheels: rubber cylinders across X with steel hubs; the fenders cover their tops
    for y in (-0.92, 0.02, 0.96):
        for s in (-1, 1):
            cyl((s * 0.66, y, 0.27), (s * 0.90, y, 0.27), 0.27, "rubber", n=12, bevel=0.02)
            cyl((s * 0.88, y, 0.27), (s * 0.93, y, 0.27), 0.11, "steel", n=8, bevel=0.01)
    box((0, 0, 0.32), (1.08, 2.6, 0.22), "frame", bevel=0.02, name="chassis")

    body = [(sx * x, y, z) for sx in (-1, 1) for x, y, z in (
        (0.58, -1.30, 0.30), (0.58, 1.36, 0.30),      # belly
        (0.74, -1.18, 0.56), (0.74, 1.44, 0.56),      # waist (widest)
        (0.56, -1.40, 0.50),                          # nose top
        (0.62, -0.54, 0.86), (0.62, 1.30, 0.86))]     # roof edge
    hull(body, "paint", bevel=0.03, emph=1.6, name="body")

    # fenders over the wheels, one sloped strip a side
    for s in (-1, 1):
        f = [(s * x, y, z) for y in (-1.30, 1.34) for x, z in ((0.70, 0.64), (0.98, 0.58), (0.98, 0.50), (0.70, 0.48))]
        hull(f, "paint2", bevel=0.015, name="fender")
        box((s * 0.80, 0.50, 0.70), (0.12, 0.62, 0.14), "paint2", bevel=0.015, name="side_box")

    # windscreen: glass in a dark frame, both lying on the glacis plane
    gn = (0.0, -0.386, 0.922)                       # glacis normal
    def on_glacis(s, x, h):
        p = glacis(s, x)
        return (p[0] + gn[0] * h, p[1] + gn[1] * h, p[2] + gn[2] * h)
    frame_pts = [on_glacis(s, x, h) for s in (0.50, 0.92) for x in (-0.46, 0.46) for h in (0.0, 0.016)]
    hull(frame_pts, "dark", name="screen_frame")
    glass = [on_glacis(s, x, h) for s in (0.55, 0.88) for x in (-0.40, 0.40) for h in (0.0, 0.024)]
    hull(glass, "glass", name="screen")

    # nose: bumper with hazard paint, headlights tucked into the corners
    box((0, -1.47, 0.36), (1.06, 0.10, 0.14), "hazard", bevel=0.015, name="bumper")
    for s in (-1, 1):
        box((s * 0.40, -1.41, 0.48), (0.14, 0.05, 0.07), "lamp", bevel=0.01, name="headlight")
        box((s * 0.52, 1.44, 0.62), (0.10, 0.05, 0.06), "lamp_red", bevel=0.01, name="taillight")

    # roof: turret ring (hull art: stays put while the turret turns), rear stowage
    cyl((PIVOT[0], PIVOT[1], 0.84), (PIVOT[0], PIVOT[1], 0.90), 0.37, "dark", n=16, bevel=0.01, name="ring")
    box((0, 1.10, 0.93), (0.92, 0.32, 0.15), "canvas", bevel=0.03, name="stowage")
    for s in (-1, 1):
        box((s * 0.34, 1.10, 1.02), (0.05, 0.36, 0.03), "leather", name="strap")
    cyl((0.52, 1.20, 0.86), (0.52, 1.20, 1.14), 0.05, "frame", n=8, bevel=0.01, name="exhaust")


def turret(ctx):
    oct8 = [(0.40, 0.0), (0.30, 0.30), (0.0, 0.42), (-0.30, 0.30), (-0.40, 0.0), (-0.30, -0.28), (0.0, -0.36),
            (0.30, -0.28)]
    pts = [(x, y + 0.04, 0.0) for x, y in oct8] + [(x * 0.80, y * 0.80 + 0.06, 0.24) for x, y in oct8]
    hull(pts, "paint", bevel=0.025, emph=1.6, name="turret")
    box((0, 0.42, 0.12), (0.46, 0.18, 0.18), "paint2", bevel=0.02, name="bustle")
    box((0, -0.36, 0.13), (0.24, 0.14, 0.16), "paint2", bevel=0.02, name="mantlet")
    cyl((0, -0.40, 0.13), (0, -1.18, 0.13), 0.042, "steel", n=10, name="barrel")
    cyl((0, -1.10, 0.13), (0, -1.26, 0.13), 0.062, "frame", n=10, bevel=0.01, name="brake")
    cyl((0.13, 0.10, 0.22), (0.13, 0.10, 0.27), 0.12, "paint2", n=12, bevel=0.012, name="hatch")
    box((-0.20, -0.02, 0.29), (0.12, 0.14, 0.09), "frame", bevel=0.012, name="sight")
    box((-0.20, -0.095, 0.29), (0.08, 0.02, 0.05), "glass", name="sight_glass")


SPRITES = [
    Sprite("Rover", hull_art, "oblique", canvas=(5, 5), footprint=(2, 3), dye=DYE,
           ship_dir="Things/Vehicles/Rover"),
    Sprite("Rover_Turret", turret, "topdown", canvas=(3, 3), graphic="single", attach="Rover", pivot=PIVOT,
           dye=DYE, ship_dir="Things/Vehicles/Rover"),
]
