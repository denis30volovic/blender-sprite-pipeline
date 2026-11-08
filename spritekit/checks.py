"""Automated checks on the finished textures (and the buffers behind them).

FAIL  missing texture or mask, wrong size, empty image, art or outline touching the texture edge (clipped),
      mask set where the texture is transparent, visible stand-in skin on a pawn sprite with allow_skin=False,
      calibration measurement off by more than 2 px
WARN  nothing dyeable in a sprite that declares a dye colour, skin check without the stand-in head mask
"""
import os

import numpy as np
from PIL import Image

from spritekit import common
from spritekit.shade import SKIN, decode

EDGE = 2          # px: the outer ring that must stay transparent
TOL = 2.0         # px: calibration tolerance


def _skin_px(buf_prefix, s, facing, variant, out):
    v = common.view_settings(s)
    B = decode(buf_prefix, v["depth_range"])
    ss = v["ss"]
    skin = (B["mat"] == SKIN).astype(np.float32)
    h, w = skin.shape[0] // ss, skin.shape[1] // ss
    skin = skin[:h * ss, :w * ss].reshape(h, ss, w, ss).mean(axis=(1, 3)) > 0.5
    note = ""
    if (s.get("layer") or "body") == "body":
        hp = os.path.join(out, "mannequin", "tex", f"MannequinHead_{facing}.png")
        if os.path.exists(hp):
            head = np.asarray(Image.open(hp).convert("RGBA"))[..., 3] > 0
            hx, hy = common.HEAD_OFFSET[variant or "Male"]
            dx = int(round(hx * v["px_per_cell"])) if facing == "east" else 0
            dy = int(round(hy * v["px_per_cell"]))
            cover = np.zeros_like(skin)
            cover[:h - dy, dx:] = head[dy:, :w - dx] if dx else head[dy:, :]
            skin &= ~cover
        else:
            note = " (no stand-in head mask: run `python pipeline.py all mannequin` to ignore what the head covers)"
    return int(skin.sum()), note


def _measure(buf_prefix, s):
    """Centre column of the buffers: rows facing up ("top") and facing the camera ("front"), in output px."""
    v = common.view_settings(s)
    B = decode(buf_prefix, v["depth_range"])
    c = B["a"].shape[1] // 2
    a, n = B["a"][:, c], B["normal"][:, c]
    return {"top": float((a & (n[:, 2] > 0.9)).sum()) / v["ss"], "front": float((a & (n[:, 1] < -0.9)).sum()) / v["ss"]}


def run(design, meta, work, out):
    tex = os.path.join(out, design, "tex")
    buf = os.path.join(work, design, "buffers")
    fails, warns, passed, ok = [], [], [], 0
    for s in meta["sprites"].values():
        W, H = common.canvas_px(s)
        dyeable = False
        for variant, frame in common.jobs(s):
            for facing in s["facings"]:
                st = common.stem(s, facing, variant, frame)
                p = os.path.join(tex, st + ".png")
                mp = os.path.join(tex, common.mask_stem(s, st) + ".png")
                if not os.path.exists(p) or not os.path.exists(mp):
                    fails.append(f"{st}: texture or mask missing (render + shade it)")
                    continue
                im = np.asarray(Image.open(p).convert("RGBA"))
                mk = np.asarray(Image.open(mp).convert("RGBA"))
                if im.shape[1] != W or im.shape[0] != H:
                    fails.append(f"{st}: {im.shape[1]}x{im.shape[0]} px, expected {W}x{H}")
                al = im[..., 3]
                if al.max() == 0:
                    fails.append(f"{st}: empty")
                    continue
                ring = np.concatenate([al[:EDGE].ravel(), al[-EDGE:].ravel(), al[:, :EDGE].ravel(), al[:, -EDGE:].ravel()])
                if ring.max() > 0:
                    fails.append(f"{st}: art touches the texture edge (clipped or outline cut off): enlarge "
                                 f"`canvas` or bring the parts in")
                if ((mk[..., 0] > 8) & (al == 0)).any():
                    fails.append(f"{st}: mask set outside the sprite")
                dyeable |= bool((mk[..., 0] > 128).any())
                if s["view"] == "pawn" and not s.get("allow_skin", True):
                    n, note = _skin_px(os.path.join(buf, st), s, facing, variant, out)
                    if note:
                        warns.append(st + note)
                    if n:
                        fails.append(f"{st}: {n} px of bare skin visible (a gap in the coverage)")
                for kind, want in ((s.get("expect") or {}).get(facing) or {}).items():
                    got = _measure(os.path.join(buf, st), s)[kind]
                    line = f"{st}: {kind} {got:.1f} px, expected {want:.1f}"
                    (fails if abs(got - want) > TOL else passed).append(line)
                ok += 1
        if s.get("ship", True) and not dyeable:
            warns.append(f"{s['name']}: nothing takes the dye (no mask red); intended?")
    for line in passed:
        print("  ok  ", line)
    for w in warns:
        print("  WARN", w)
    for f in fails:
        print("  FAIL", f)
    print(f"check {design}: {ok} textures, {len(fails)} failures, {len(warns)} notes")
    return fails
