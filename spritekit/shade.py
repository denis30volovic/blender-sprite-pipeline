"""Numpy side: G-buffers -> finished RimWorld-style texture + dye mask. All style decisions live here, so a
look change is a re-shade (seconds), never a re-render.

The look (flat-facet, as measured on vanilla and well-made modded sprites):
- each material has one face-on colour; a face's tone steps away from it by how far its normal turns toward or
  away from the light, clamped to one step (two for emph > 1 parts), so surfaces stay flat but read as solid;
- a dark line on the far side of every depth step (where one part stands in front of another) and a thin seam
  where two material groups meet;
- a solid near-black outline drawn outside the silhouette;
- no cast shadows, ambient occlusion, speculars or noise;
- supersampled buffers box-filtered down with premultiplied alpha.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

from spritekit import common
from spritekit.materials import HAZARD_PERIOD, HAZARD_RGB, MATERIALS, NAMES, OUTLINE_RGB, STEP, TONES

LINE_STEP = 0.020     # cells: dark line on the far side of a depth step
LINE_SEAM = 0.010     # cells: seam between material groups (total width)
STEP_MIN = 0.045      # cells of depth that count as a step
INK_STEP = 0.45       # line colour = local colour x this
INK_SEAM = 0.62

_M = [MATERIALS[n] for n in NAMES]
RGB = np.array([m["rgb"] for m in _M], np.float32)
MASK = np.array([-1 if m.get("mask") is None else m["mask"] for m in _M])
UNLIT = np.array([bool(m.get("unlit")) for m in _M])
CUT = np.array([bool(m.get("cutout")) for m in _M])
HAZ = np.array([m.get("pattern") == "hazard" for m in _M])
_GROUPS = sorted({m.get("group", n) for n, m in zip(NAMES, _M)})
GROUP = np.array([_GROUPS.index(m.get("group", n)) for n, m in zip(NAMES, _M)])
SKIN = NAMES.index("skin")
_TONE_LUT = np.array([TONES[k] for k in (-2, -1, 0, 1, 2)], np.float32)


def decode(prefix, depth_range):
    """Read <prefix>_{id,normal,depth}.png. Raises if the id pass is not exact (colour management touched it)."""
    idp = np.asarray(Image.open(prefix + "_id.png").convert("RGBA")).astype(np.int32)
    nrm = np.asarray(Image.open(prefix + "_normal.png").convert("RGB")).astype(np.float32) / 255.0 * 2.0 - 1.0
    dep = np.asarray(Image.open(prefix + "_depth.png").convert("RGBA")).astype(np.float32)
    a = idp[..., 3] > 127
    bad = a & (idp[..., 0] % common.ID_STEP != 0)
    if bad.sum() > 0.001 * max(a.sum(), 1):
        raise RuntimeError(f"{prefix}_id.png: material ids are not multiples of {common.ID_STEP}; the render "
                           "was colour-managed or filtered (view transform must be Raw, dither 0, 1 sample)")
    mat = np.where(a, np.clip(np.rint(idp[..., 0] / common.ID_STEP).astype(np.int32) - 1, 0, len(NAMES) - 1), -1)
    emph = idp[..., 1] / common.EMPH_SCALE
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
    depth = (dep[..., 0] + dep[..., 1] / 255.0) / 255.0 * 2.0 * depth_range - depth_range
    return dict(a=a, mat=mat, emph=emph, normal=nrm, depth=depth)


def downsample(x, ss):
    h, w = x.shape[0] // ss, x.shape[1] // ss
    x = x[:h * ss, :w * ss]
    return x.reshape(h, ss, w, ss, *x.shape[2:]).mean(axis=(1, 3))


def shade(prefix, sprite, out_path):
    """Shade one facing. Writes out_path (RGBA) and its mask beside it; returns a few stats."""
    v = common.view_settings(sprite)
    ss, ppc = v["ss"], v["px_per_cell"]
    hp = ppc * ss                         # hi-res px per cell
    B = decode(prefix, v["depth_range"])
    a, mat = B["a"], B["mat"]
    mi = np.maximum(mat, 0)
    cut = a & CUT[mi]
    solid = a & ~cut

    light = np.asarray(v["light"], np.float32)
    light /= np.linalg.norm(light)
    f0 = float(np.dot(np.asarray(v["face_on"], np.float32), light))
    ndl = B["normal"] @ light
    idx = np.rint((ndl - f0) / STEP * np.maximum(B["emph"], 0.01))
    lim = np.where(B["emph"] > 1.05, 2, 1)
    idx = np.clip(idx, -lim, lim).astype(np.int32)
    idx[UNLIT[mi]] = 0
    mult = _TONE_LUT[idx + 2]
    rgb = RGB[mi] * mult[..., None]

    haz = solid & HAZ[mi]
    if haz.any():
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
        stripe = (((xx + yy) / (HAZARD_PERIOD * hp)) % 1.0) < 0.5
        sel = haz & stripe
        rgb[sel] = np.asarray(HAZARD_RGB, np.float32) * mult[sel][:, None]

    near = np.where(solid, B["depth"], -1e9)
    r = max(1, int(round(LINE_STEP * hp)))
    step = solid & (ndimage.maximum_filter(near, size=2 * r + 1) - near > STEP_MIN)
    gid = np.where(solid, GROUP[mi], -1)
    if solid.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        gid = gid[iy, ix]
    k = max(1, int(round(LINE_SEAM * hp / 2))) * 2 + 1
    seam = solid & ((ndimage.maximum_filter(gid, size=k) != gid) | (ndimage.minimum_filter(gid, size=k) != gid))
    rgb[seam & ~step] *= INK_SEAM
    rgb[step] *= INK_STEP

    ol = ~solid & (ndimage.distance_transform_edt(~solid) <= v["outline"] * hp)
    A = (solid | ol).astype(np.float32)
    rgb[ol] = OUTLINE_RGB
    rgb[~(solid | ol)] = 0
    m1 = (solid & (MASK[mi] == 0)).astype(np.float32)
    m2 = (solid & (MASK[mi] == 1)).astype(np.float32)

    Ad = downsample(A, ss)
    with np.errstate(invalid="ignore", divide="ignore"):
        col = np.where(Ad[..., None] > 0, downsample(rgb * A[..., None], ss) / np.maximum(Ad[..., None], 1e-6), 0)
        md = [np.where(Ad > 0, downsample(m * A, ss) / np.maximum(Ad, 1e-6), 0) for m in (m1, m2)]
    tex = np.dstack([col / 255.0, Ad])
    Image.fromarray((np.clip(tex, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(out_path)
    mask = np.dstack([md[0], md[1], np.zeros_like(Ad), Ad])
    mpath = out_path[:-4]
    mpath = (mpath + "_m.png") if sprite["graphic"] == "single" else (mpath + "m.png")
    Image.fromarray((np.clip(mask, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(mpath)
    return dict(skin_px=int((a & (mat == SKIN)).sum() // (ss * ss)), solid_px=int(solid.sum() // (ss * ss)))
