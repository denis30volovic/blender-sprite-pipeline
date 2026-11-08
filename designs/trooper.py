"""Trooper: a light armour set, body armour for all five body types plus a full helmet (worked apparel example).

Rules this design follows (they apply to any apparel):
- One build function serves every body type: shapes are placed from the body's anchors (shoulder_z, waist_z,
  hip_z) and local width, rigid parts scale with the body width.
- The head layer hides the upper chest in south and north, so the set's identity lives where it stays visible:
  shoulders (out past the head), waist, belt, back pack.
- The stand-in body is rendered as a cutout ("skin"): it hides what is behind it and any of it left visible is a
  coverage gap (allow_skin=False makes that a check failure).
- The helmet covers the whole stand-in head, its visor sits on the eye line (eye_z), the face projects forward and
  the back of the skull is a rounded mass, and the body under the head cuts away anything behind the neck.
"""
from spritekit.kit import BODY_TYPES, Body, Ellipsoid, Head, Sprite, V, body_below_head, box, cyl, ellipsoid, \
    linspace, loft, plate, rot

DYE = (118, 128, 104)


def armour(ctx):
    b = Body(ctx.variant)
    b.skin()
    k = b.width(b.chest_z) / 0.265                       # 1.0 on Male; rigid parts scale with it
    zs = linspace(b.top_z, b.bottom_z, 16)
    loft([b.ring(z, 0.006, 32) for z in zs], "cloth", smooth=True, name="undersuit")

    # chest plate: a shield shape wrapped on the torso, few facets, emph 1.6 so its planes read
    top, low = b.shoulder_z + 0.02, b.waist_z + 0.03
    mid = (top + low) / 2
    plate(b, -66, 66, top, low, 0.010, 0.030, "paint", grid=(4, 2), emph=1.6,
          outline=[(-66, top), (66, top), (66, mid), (0, low), (-66, mid)], name="chest")
    # two abdomen bands under it, each a little narrower
    for i, (z0, z1) in enumerate(((b.waist_z + 0.02, b.waist_z - 0.05), (b.waist_z - 0.06, b.hip_z + 0.03))):
        w = 52 - 8 * i
        plate(b, -w, w, z0, z1, 0.012, 0.022, "paint2", grid=(3, 1), name=f"band{i}")

    # belt with pouches and a buckle
    zb0, zb1 = b.hip_z + 0.015, b.hip_z - 0.035
    loft([b.ring(zb0, 0.028, 32), b.ring(zb1, 0.030, 32)], "leather", name="belt")
    zc = (zb0 + zb1) / 2
    for th in (-58, -32, 32, 58):
        p = b.point(th, zc - 0.01, 0.03)
        n = b.normal(th, zc)
        box(p + n * 0.03, (0.075 * k, 0.06, 0.085), "canvas", bevel=0.01, r=rot(z=th), name="pouch")
        box(p + n * 0.035 + V(0, 0, 0.035), (0.08 * k, 0.07, 0.03), "paint2", bevel=0.006, r=rot(z=th), name="flap")
    p = b.point(0, zc, 0.03)
    box(p + V(0, -0.012, 0), (0.06, 0.02, 0.05), "steel", bevel=0.006, name="buckle")

    # low rounded shoulder caps that hug the arm (no spikes, no stacked pauldrons)
    for s in (-1, 1):
        p = b.point(s * 84, b.shoulder_z + 0.005, 0.0)
        ellipsoid((p.x, p.y, p.z), (0.085 * k, 0.115 * k, 0.06), "paint", segments=10, rings=8,
                  cut_below=-0.025, emph=1.6, name="shoulder")
        ellipsoid((p.x + s * 0.015, p.y, p.z - 0.045), (0.075 * k, 0.10 * k, 0.045), "paint2", segments=10,
                  rings=6, cut_below=-0.02, name="shoulder_lower")

    # back pack: shows in north and in east behind the body, the same object in both
    p = b.point(180, b.chest_z - 0.06, 0.0)
    w = 0.32 * k
    box((p.x, p.y + 0.06, p.z), (w, 0.12, 0.30), "canvas", bevel=0.02, name="pack")
    box((p.x, p.y + 0.125, p.z + 0.05), (w * 0.8, 0.03, 0.14), "paint2", bevel=0.008, name="pack_lid")
    for s in (-1, 1):
        box((p.x + s * w * 0.42, p.y + 0.09, p.z - 0.06), (0.05, 0.06, 0.12), "canvas", bevel=0.01, name="side_pocket")


def helmet(ctx):
    Head().skin()
    body_below_head()
    S = Ellipsoid((0.0, 0.012, 0.065), (0.295, 0.29, 0.32))     # helmet surface just outside the stand-in head
    v_eye = -14.0                                                # elevation of the eye line on S (front)
    ellipsoid(S.c, S.r, "paint", segments=14, rings=10, cut_below=-0.08, emph=1.5, name="dome")
    plate(S, 58, 302, -64, -4, 0.0, 0.026, "paint", grid=(8, 2), emph=1.5, name="skirt")
    # visor band; the brow above and the face plate below overlap its edges, so no gap can open
    plate(S, -64, 64, v_eye - 8, v_eye + 8, 0.002, 0.010, "dark", grid=(6, 1), name="visor")
    plate(S, -70, 70, v_eye + 5, v_eye + 16, 0.002, 0.030, "paint2", grid=(6, 1), emph=1.6,
          outline=[(-70, v_eye + 5), (70, v_eye + 5), (58, v_eye + 16), (-58, v_eye + 16)], name="brow")
    plate(S, -64, 64, -74, v_eye - 5, 0.004, 0.034, "paint2", grid=(4, 3), emph=1.6,
          outline=[(-64, v_eye - 5), (64, v_eye - 5), (64, -58), (36, -74), (-36, -74), (-64, -58)], name="face")
    for s in (-1, 1):
        cyl((s * 0.30, 0.03, -0.03), (s * 0.365, 0.03, -0.03), 0.062, "frame", n=10, bevel=0.008, name="ear")


SPRITES = [
    Sprite("TrooperArmor", armour, "pawn", canvas=(1.5, 1.5), variants=BODY_TYPES, layer="body", dye=DYE,
           icon=True, allow_skin=False, ship_dir="Things/Apparel/Trooper/TrooperArmor"),
    Sprite("TrooperHelmet", helmet, "pawn", canvas=(1.5, 1.5), layer="head", dye=DYE, icon=True,
           allow_skin=False, ship_dir="Things/Apparel/Trooper/TrooperHelmet"),
]
