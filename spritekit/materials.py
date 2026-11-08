"""Material table shared by both sides (plain Python).

A design tags every part with one of these names. Blender writes the index into the id pass; shade.py turns it
into colour, tone steps, lines and the dye mask. Add materials at the end of the table (the index is the id).

  rgb      face-on colour (0..255). Dyeable materials are near-white: the game multiplies them by the dye.
  mask     0 = dyed by the first colour (mask R), 1 = second colour (mask G), None = keeps its colour.
  group    line group: a thin seam line is drawn where two different groups meet.
  unlit    always the face-on colour (lamps, glow).
  cutout   occludes what is behind it but is never drawn (stand-in body for apparel). "skin" pixels that stay
           visible are coverage gaps and are counted by the checks; "occluder" pixels are not.
  pattern  "hazard": diagonal black stripes painted in screen space.
"""

MATERIALS = {
    "paint": dict(rgb=(226, 226, 220), mask=0, group="paint"),
    "paint2": dict(rgb=(186, 186, 180), mask=0, group="paint"),
    "stripe": dict(rgb=(226, 226, 220), mask=1, group="paint"),
    "concrete": dict(rgb=(158, 156, 148), group="stone"),
    "frame": dict(rgb=(98, 100, 104), group="metal"),
    "steel": dict(rgb=(158, 160, 164), group="metal"),
    "dark": dict(rgb=(54, 55, 58), group="dark"),
    "rubber": dict(rgb=(50, 50, 52), group="dark"),
    "cloth": dict(rgb=(96, 100, 86), group="cloth"),
    "canvas": dict(rgb=(146, 132, 100), group="cloth"),
    "leather": dict(rgb=(112, 86, 62), group="cloth"),
    "glass": dict(rgb=(74, 96, 112), group="glass"),
    "hazard": dict(rgb=(226, 182, 58), group="paint", pattern="hazard"),
    "lamp": dict(rgb=(255, 236, 170), unlit=True, group="lamp"),
    "lamp_red": dict(rgb=(228, 66, 48), unlit=True, group="lamp"),
    "flesh": dict(rgb=(214, 180, 150), group="flesh"),
    "skin": dict(rgb=(255, 0, 255), cutout=True, group="cut"),
    "occluder": dict(rgb=(0, 255, 255), cutout=True, group="cut"),
}

NAMES = list(MATERIALS)

# Tone multipliers per step away from the face-on value. Ordinary parts are clamped to one step, parts with
# emph > 1 to two: "flat, but important parts have depth".
TONES = {-2: 0.64, -1: 0.80, 0: 1.0, 1: 1.10, 2: 1.18}
STEP = 0.22                 # change of n.L per tone step

OUTLINE_RGB = (18, 17, 16)
HAZARD_PERIOD = 0.16        # cells per stripe pair
HAZARD_RGB = (28, 26, 24)
