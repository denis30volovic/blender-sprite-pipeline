"""Relay: a 2x2 radio relay building with a turning radar antenna (worked building + animation example).

The still (ctx.frame is None) is the shipped Graphic_Multi texture set; `frames=8` also renders the antenna
turning through 180 degrees (it is symmetric, so that loops), shipped to a Frames/ subfolder. Everything but the
antenna is identical in every frame, so a game-side component can swap only the frame texture.

Building rules: stuff-coloured parts are "paint" (dyed by the mask, the game tints them with the material
colour), the concrete plinth and bare metal keep their colour, one accent (the red beacon) at most.
"""
from spritekit.kit import Sprite, V, box, cyl, frustum, hull, rot

MAST = (0.48, 0.38)
DYE = (150, 128, 100)


def antenna(angle, top):
    """Reflector bar on a yoke, turned `angle` degrees about the mast; points built at the origin, then moved."""
    r = rot(z=angle)
    def place(p):
        return V(top) + r @ V(p)
    box(place((0, 0, 0.05)), (0.16, 0.16, 0.10), "frame", bevel=0.015, r=r, name="yoke")
    dish = [(x, y, z) for x in (-0.46, -0.30, 0.30, 0.46) for y, z in ((0.0, 0.10), (0.06, 0.26), (0.0, 0.30))]
    dish = [(x, y + (0.03 if abs(x) > 0.4 else 0.0), z - (0.04 if abs(x) > 0.4 else 0.0)) for x, y, z in dish]
    dish += [(x, y + 0.05, z) for x, y, z in dish]
    hull([place(p) for p in dish], "paint2", bevel=0.012, emph=2.0, name="reflector")
    box(place((0, -0.10, 0.20)), (0.08, 0.10, 0.06), "dark", bevel=0.01, r=r, name="feed")
    cyl(place((0, 0.03, 0.30)), place((0, 0.03, 0.36)), 0.035, "lamp_red", n=8, name="beacon")


def relay(ctx):
    frustum((0, 0, 0), (1.94, 1.94), (1.84, 1.84), 0.12, "concrete", bevel=0.02, name="plinth")
    box((0, -0.955, 0.06), (1.6, 0.03, 0.07), "hazard", name="edge_paint")

    # equipment cabinet: one tapered block with a roof cap, vents and a door set into its front
    frustum((-0.36, 0.12, 0.12), (0.98, 1.24), (0.90, 1.16), 0.64, "paint", bevel=0.02, emph=1.6, name="cabinet")
    frustum((-0.36, 0.12, 0.76), (0.96, 1.22), (0.84, 1.10), 0.07, "paint2", bevel=0.015, name="roof")
    front = 0.12 - 0.60
    box((-0.58, front - 0.01, 0.46), (0.32, 0.04, 0.46), "paint2", bevel=0.01, name="door")
    box((-0.46, front - 0.035, 0.46), (0.03, 0.03, 0.10), "steel", name="handle")
    for i in range(3):
        box((-0.10, front - 0.012, 0.30 + 0.12 * i), (0.30, 0.04, 0.06), "dark", name="vent")
    box((-0.50, 0.30, 0.86), (0.34, 0.22, 0.09), "frame", bevel=0.012, name="roof_unit")
    box((-0.50, 0.185, 0.86), (0.26, 0.02, 0.05), "dark", name="roof_grille")

    # mast with a flange, conduit to the cabinet, battery boxes by the front
    cyl((*MAST, 0.12), (*MAST, 0.20), 0.17, "frame", n=12, bevel=0.015, name="flange")
    cyl((*MAST, 0.20), (*MAST, 1.12), 0.085, "steel", r1=0.06, n=10, name="mast")
    box(((MAST[0] - 0.10) / 2 + 0.04, 0.38, 0.16), (0.42, 0.08, 0.06), "frame", name="conduit")
    for x in (0.34, 0.66):
        box((x, -0.62, 0.22), (0.24, 0.28, 0.20), "steel", bevel=0.02, name="battery")
        box((x, -0.62, 0.335), (0.12, 0.08, 0.03), "dark", name="terminal")

    angle = 180.0 * ctx.t if ctx.frame is not None else 30.0
    antenna(angle, (*MAST, 1.10))


SPRITES = [
    Sprite("Relay", relay, "oblique", canvas=(3, 4), footprint=(2, 2), frames=8, dye=DYE,
           ship_dir="Things/Building/Relay"),
]
