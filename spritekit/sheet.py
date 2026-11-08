"""Review sheets: what an agent (or a person) looks at to judge a design.

out/<design>/sheet.png  every sprite, plain and dyed, S / E / N / W (west = east mirrored, as the game does),
                        turrets drawn on their hulls, pawn apparel on the stand-in pawn, footprint grid, 1:1 scale
out/<design>/zoom.png   south and east enlarged, for detail and line work
out/<design>/<Sprite>_anim_<facing>.gif   animation frames, when a sprite has them
"""
import os

import numpy as np
from PIL import Image, ImageDraw

from spritekit import common

BG = (92, 98, 84)
GRID = (104, 111, 95)
FOOT = (142, 150, 112)
TEXT = (236, 236, 226)
PAWN_TILE = 190
GAP = 16


def _load(tex, s, st):
    p = os.path.join(tex, st + ".png")
    if not os.path.exists(p):
        return None
    return Image.open(p).convert("RGBA"), Image.open(os.path.join(tex, common.mask_stem(s, st) + ".png")).convert("RGBA")


def dyed(img, mask, c1, c2=None):
    a = np.asarray(img).astype(np.float32)
    m = np.asarray(mask).astype(np.float32) / 255.0
    f = 1 - m[..., 0:1] + m[..., 0:1] * np.asarray(c1, np.float32) / 255.0
    if c2 is not None:
        f = f * (1 - m[..., 1:2] + m[..., 1:2] * np.asarray(c2, np.float32) / 255.0)
    a[..., :3] *= f
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")


def _get(tex, s, facing, variant=None, frame=None, dye=False):
    r = _load(tex, s, common.stem(s, facing, variant, frame))
    if r is None:
        return None
    img, mask = r
    return dyed(img, mask, s["dye"], s.get("dye2")) if dye else img


def thing(meta, tex, s, facing, variant=None, frame=None, dye=False):
    """A building/vehicle facing as the game layers it: the sprite plus anything attached to it (turrets,
    pointing the way the thing faces, at the pivot's screen offset). West is east mirrored."""
    src = "east" if facing == "west" else facing
    base = _get(tex, s, src, variant, frame, dye)
    if base is None:
        return None
    kids = [k for k in meta["sprites"].values() if k.get("attach") == s["name"]]
    v = common.view_settings(s)
    pad = max([max(common.canvas_px(k)) // 2 for k in kids] + [0])
    im = Image.new("RGBA", (base.size[0] + 2 * pad, base.size[1] + 2 * pad), (0, 0, 0, 0))
    im.alpha_composite(base, (pad, pad))
    for k in kids:
        t = _get(tex, k, k["facings"][0], dye=dye)
        if t is None:
            continue
        t = t.rotate({"north": 0, "east": -90, "south": 180}[src], resample=Image.BICUBIC)
        ox, oy = common.oblique_offset(k["pivot"], common.FACING_YAW[src], v.get("elev", 90.0))
        cx = im.size[0] / 2 + ox * v["px_per_cell"]
        cy = im.size[1] / 2 - oy * v["px_per_cell"]
        im.alpha_composite(t, (int(round(cx - t.size[0] / 2)), int(round(cy - t.size[1] / 2))))
    return im.transpose(Image.FLIP_LEFT_RIGHT) if facing == "west" else im


def _ground(size, s, facing):
    """Background with the cell grid and the footprint, aligned to the image centre (the model origin)."""
    bg = Image.new("RGB", size, BG)
    fp = s.get("footprint")
    if not fp:
        return bg
    ppc = common.view_settings(s)["px_per_cell"]
    w, h = (fp[1], fp[0]) if facing in ("east", "west") else fp
    cx, cy = size[0] / 2, size[1] / 2
    dr = ImageDraw.Draw(bg)
    for i in range(-20, 21):
        x = cx + (i - w / 2) * ppc
        y = cy + (i - h / 2) * ppc
        dr.line([(x, 0), (x, size[1])], fill=GRID)
        dr.line([(0, y), (size[0], y)], fill=GRID)
    dr.rectangle([cx - w / 2 * ppc, cy - h / 2 * ppc, cx + w / 2 * ppc, cy + h / 2 * ppc], outline=FOOT, width=2)
    return bg


def _row(tiles, label):
    tiles = [t for t in tiles if t is not None]
    if not tiles:
        return None
    W = sum(t.size[0] for t in tiles) + GAP * (len(tiles) + 1)
    H = max(t.size[1] for t in tiles) + GAP + 18
    row = Image.new("RGB", (W, H), (40, 42, 40))
    ImageDraw.Draw(row).text((GAP, 3), label, fill=TEXT)
    x = GAP
    for t in tiles:
        row.paste(t, (x, 18 + H - 18 - GAP - t.size[1] + GAP // 2))
        x += t.size[0] + GAP
    return row


def _stack(rows):
    rows = [r for r in rows if r is not None]
    W = max(r.size[0] for r in rows)
    out = Image.new("RGB", (W, sum(r.size[1] for r in rows)), (40, 42, 40))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.size[1]
    return out


def _on_ground(im, s, facing):
    if im is None:
        return None
    bg = _ground(im.size, s, facing)
    bg.paste(im, (0, 0), im)
    return bg


def _union_box(tiles, pad=32):
    """Union of the tiles' opaque boxes plus a margin, clamped to the image: crop every tile of a row with it so
    the row is compact and the facings stay aligned to the same ground grid."""
    boxes = [t.getbbox() for t in tiles if t is not None and t.getbbox()]
    W, H = next(t.size for t in tiles if t is not None)
    if not boxes:
        return (0, 0, W, H)
    return (max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad),
            min(W, max(b[2] for b in boxes) + pad), min(H, max(b[3] for b in boxes) + pad))


def thing_rows(meta, tex, s, out_dir):
    rows = []
    facings = list(s["facings"]) + (["west"] if "east" in s["facings"] and s["graphic"] != "single" else [])
    variants = s.get("variants") or [None]
    for variant in variants:
        for dye in (False, True):
            tiles = [thing(meta, tex, s, f, variant, None, dye) for f in facings]
            box = _union_box(tiles)
            tiles = [_on_ground(t, s, f).crop(box) if t is not None else None for t, f in zip(tiles, facings)]
            label = f"{s['name']}{' ' + variant if variant else ''}  {'dyed' if dye else 'plain'}  " \
                    f"{' / '.join(f[0].upper() for f in facings)}  1:1 ({s['view']}, {s['canvas'][0]}x{s['canvas'][1]} cells)"
            rows.append(_row(tiles, label))
    if s.get("frames"):
        n = s["frames"]
        for facing in s["facings"]:
            frames = [thing(meta, tex, s, facing, variants[0], k, True) for k in range(n)]
            frames = [f for f in frames if f is not None]
            if not frames:
                continue
            box = _union_box(frames)
            frames = [_on_ground(f, s, facing).crop(box) for f in frames]
            frames[0].save(os.path.join(out_dir, f"{s['name']}_anim_{facing}.gif"), save_all=True,
                           append_images=frames[1:], duration=110, loop=0)
            if facing == s["facings"][0]:
                rows.append(_row(frames, f"{s['name']} frames 0-{n - 1} ({facing}, dyed)"))
    return rows


def pawn_tile(meta, tex, under, bt, facing, dye):
    """Body-layer sprites over the stand-in body, head-layer sprites at the head offset, like the game."""
    sprites = [s for s in meta["sprites"].values() if s["view"] == "pawn"]
    if not sprites:
        return None
    src = "east" if facing == "west" else facing
    ppc = common.view_settings(sprites[0])["px_per_cell"]
    size = common.canvas_px(sprites[0])
    hx, hy = common.HEAD_OFFSET[bt]
    lift = int(round(hy * ppc))
    im = Image.new("RGBA", (size[0], size[1] + lift), (0, 0, 0, 0))
    layers = []
    if under:
        layers += [(under, {"name": "Mannequin", "graphic": "multi", "layer": "body", "dye": [255] * 3}, bt),
                   (under, {"name": "MannequinHead", "graphic": "multi", "layer": "head", "dye": [255] * 3}, None)]
    layers += [(tex, s, bt if s.get("variants") else None) for s in sprites]
    for layer in ("body", "head"):
        for d, s, variant in layers:
            if (s.get("layer") or "body") != layer:
                continue
            r = _get(d, s, src, variant, None, dye and d == tex)
            if r is None:
                continue
            if layer == "body":
                im.alpha_composite(r, (0, lift))
            else:
                im.alpha_composite(r, (int(round(hx * ppc)) if src == "east" else 0, 0))
    if facing == "west":
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    bg = Image.new("RGB", im.size, BG)
    bg.paste(im, (0, 0), im)
    return bg


def pawn_rows(design, meta, tex, out):
    under = os.path.join(out, "mannequin", "tex") if design != "mannequin" else None
    if under and not os.path.isdir(under):
        print("  (no stand-in pawn under the apparel: run `python pipeline.py all mannequin` once)")
        under = None
    bodies = [s for s in meta["sprites"].values() if s["view"] == "pawn" and s.get("variants")]
    variants = bodies[0]["variants"] if bodies else ["Male"]
    facings = ["south", "east", "north", "west"]
    rows = []
    for bt in variants:
        tiles = [pawn_tile(meta, tex, under, bt, f, False) for f in facings] + \
                [pawn_tile(meta, tex, under, bt, f, True) for f in facings]
        tiles = [t.resize((PAWN_TILE, int(t.size[1] * PAWN_TILE / t.size[0])), Image.LANCZOS) for t in tiles if t]
        rows.append(_row(tiles, f"{bt}:  S / E / N / W plain  |  S / E / N / W dyed"))
    zoom = [pawn_tile(meta, tex, under, variants[0], f, True) for f in ("south", "east")]
    return rows, [z for z in zoom if z]


def build(design, meta, out):
    tex = os.path.join(out, design, "tex")
    out_dir = os.path.join(out, design)
    rows, zoom = [], []
    pawn = [s for s in meta["sprites"].values() if s["view"] == "pawn"]
    if pawn:
        r, z = pawn_rows(design, meta, tex, out)
        rows += r
        zoom += z
    for s in meta["sprites"].values():
        if s["view"] == "pawn" or s.get("attach"):
            continue
        rows += thing_rows(meta, tex, s, out_dir)
        for f in ("south", "east"):
            if f in s["facings"] or (f == "south" and s["graphic"] == "single" and f == "south"):
                im = thing(meta, tex, s, f, (s.get("variants") or [None])[0], None, True)
                if im is not None and im.getbbox():
                    im = im.crop(im.getbbox())
                    zoom.append(_on_ground(im, {}, f).resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST))
        if s["graphic"] == "single":
            im = thing(meta, tex, s, s["facings"][0], None, None, True)
            if im is not None and im.getbbox():
                im = im.crop(im.getbbox())
                zoom.append(_on_ground(im, {}, "north").resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST))
    for k in [s for s in meta["sprites"].values() if s.get("attach")]:
        rows.append(_row([_on_ground(_get(tex, k, k["facings"][0], dye=d), k, "north") for d in (False, True)],
                         f"{k['name']} alone (attached to {k['attach']})  plain / dyed"))
    paths = []
    if rows:
        p = os.path.join(out_dir, "sheet.png")
        _stack(rows).save(p, optimize=True)
        paths.append(p)
    if zoom:
        H = max(z.size[1] for z in zoom)
        zs = Image.new("RGB", (sum(z.size[0] for z in zoom) + GAP * (len(zoom) + 1), H + 2 * GAP), (40, 42, 40))
        x = GAP
        for z in zoom:
            zs.paste(z, (x, GAP))
            x += z.size[0] + GAP
        p = os.path.join(out_dir, "zoom.png")
        zs.save(p, optimize=True)
        paths.append(p)
    return paths


def icon(src, mask_src, dst_stem, size=256, margin=0.07):
    """Square icon cut from a facing: <dst_stem>.png and <dst_stem>_m.png."""
    im, mk = Image.open(src).convert("RGBA"), Image.open(mask_src).convert("RGBA")
    x0, y0, x1, y1 = im.getbbox()
    side = int(max(x1 - x0, y1 - y0) / (1 - 2 * margin))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    for img, path in ((im, dst_stem + ".png"), (mk, dst_stem + "_m.png")):
        c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        c.paste(img.crop(box), (0, 0))
        c.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA").save(path, optimize=True)
