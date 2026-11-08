"""Plain-Python facts shared by the Blender side and the numpy side (no bpy, no numpy here).

Everything the two sides must agree on lives in this file or in materials.py: view types, facings, buffer
encodings and output file names. The Blender side writes buffers + meta.json; the numpy side reads only those.
"""
import math

FACING_YAW = {"south": 0.0, "east": 90.0, "north": 180.0}

# Per view type: default output density, supersampling, light, the "face-on" normal that gets the base tone,
# camera angle, depth packing range (cells either side of the origin) and outline width (cells).
VIEWS = {
    # pawn apparel: ortho camera tilted down 12 deg; the model's vertical axis is stretched by 1/cos(tilt) so
    # heights stay true on the image. 1.5-cell canvas at 512 px = 341.33 px per cell.
    "pawn": dict(px_per_cell=512 / 1.5, ss=3, tilt=12.0, face_on=(0.0, -1.0, 0.0),
                 light=(-0.30, -0.72, 0.62), depth_range=2.0, outline=0.035),
    # buildings and vehicle hulls: ortho camera at `elev` above the ground, rendered with non-square pixels so the
    # ground plane keeps its full length and vertical faces show at cot(elev) of their height.
    "oblique": dict(px_per_cell=128, ss=3, elev=60.0, face_on=(0.0, 0.0, 1.0),
                    light=(-0.30, 0.62, 0.72), depth_range=16.0, outline=0.032),
    # turrets, roofs, top-down props: straight down, north (+Y) up the image.
    "topdown": dict(px_per_cell=128, ss=3, face_on=(0.0, 0.0, 1.0),
                    light=(-0.30, 0.62, 0.72), depth_range=16.0, outline=0.032),
}

PASSES = ("id", "normal", "depth")

# id pass: R = (material index + 1) * ID_STEP, G = emph * EMPH_SCALE, A = coverage
ID_STEP = 8
EMPH_SCALE = 100

# Pawn layout (approximate vanilla values; check BodyTypeDef.headOffset for your game version).
BODY_TYPES = ["Male", "Female", "Thin", "Hulk", "Fat"]
HEAD_OFFSET = {"Male": (0.04, 0.34), "Female": (0.10, 0.34), "Thin": (0.09, 0.34), "Hulk": (0.10, 0.34),
               "Fat": (0.09, 0.34)}


def view_settings(sprite):
    """The sprite's view defaults with its own overrides applied."""
    v = dict(VIEWS[sprite["view"]])
    for k in ("px_per_cell", "ss", "elev", "tilt", "outline", "light", "face_on", "depth_range"):
        if sprite.get(k) is not None:
            v[k] = sprite[k]
    return v


def canvas_px(sprite):
    v = view_settings(sprite)
    w, h = sprite["canvas"]
    return int(round(w * v["px_per_cell"])), int(round(h * v["px_per_cell"]))


def stem(sprite, facing, variant=None, frame=None):
    """Output file name without extension. Graphic_Multi: <Name>[_<Variant>][_fNN]_<facing>;
    Graphic_Single: <Name>[_<Variant>][_fNN]."""
    parts = [sprite["name"]]
    if variant:
        parts.append(variant)
    if frame is not None:
        parts.append(f"f{frame:02d}")
    if sprite["graphic"] != "single":
        parts.append(facing)
    return "_".join(parts)


def mask_stem(sprite, s):
    """RimWorld mask naming: Graphic_Multi <tex>_<facing>m, Graphic_Single <tex>_m."""
    return s + ("_m" if sprite["graphic"] == "single" else "m")


def jobs(sprite):
    """Every (variant, frame) the sprite renders; frame None is the still (rest pose)."""
    variants = sprite.get("variants") or [None]
    frames = [None] + list(range(sprite.get("frames") or 0))
    return [(v, f) for v in variants for f in frames]


def oblique_offset(point, yaw_deg, elev_deg):
    """Hull-frame point (cells) -> screen offset (cells, x right, y up) from the image centre in an oblique view
    turned to a facing. This is what a turret's draw offset per facing is."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    x, y = point[0] * c - point[1] * s, point[0] * s + point[1] * c
    return x, y + point[2] / math.tan(math.radians(elev_deg))
