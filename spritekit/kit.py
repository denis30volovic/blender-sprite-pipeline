"""kit: geometry builders for sprite designs. Runs inside Blender only (bpy, bmesh, mathutils).

A design module does `from spritekit.kit import *`, defines build functions that take a Ctx, and lists its
outputs in SPRITES. Units are cells everywhere: 1 Blender unit = 1 map cell. Axes: +X = the model's left side
(screen right in the south view), -Y = the model's front (toward the viewer in south), +Z = up. Ground is z = 0
for buildings and vehicles; pawn sprites are centred on the canvas centre (origin = canvas centre).

Every builder returns the new object and tags it with a material name (materials.py) and an emphasis:
emph 1 = ordinary part (one tone step either way), emph 2 = identity part (two steps). Few, large faces read as
deliberate planes; that is the look, so prefer hull/box/prism with a small bevel over smooth subdivided shapes.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from spritekit.common import BODY_TYPES, HEAD_OFFSET, VIEWS
from spritekit.materials import MATERIALS

PARTS = []
_ROOT = [None]


# ------------------------------------------------------------------ sprite declarations

class Sprite:
    """One output texture set.

    name       file name stem (CamelCase, unique in the game's texture folder)
    build      function(ctx) that builds the geometry with the kit
    view       "pawn" | "oblique" | "topdown" (camera, light, density: common.VIEWS)
    canvas     (w, h) in cells; the image centre is the model origin
    facings    which of south/east/north to render (the game mirrors east for west)
    variants   e.g. body types; ctx.variant is set to each, file names get _<Variant>
    frames     animation frames rendered as well as the still (ctx.t goes 0 .. (n-1)/n)
    graphic    "multi" (one texture per facing) or "single" (one texture, <Name>.png + <Name>_m.png)
    layer      pawn sprites: "body" or "head" (head sprites sit at the body type's head offset in previews)
    footprint  (w, h) cells of the thing's footprint: drawn as a grid in review sheets
    attach     name of the sprite this one is drawn on (turret on a hull), at `pivot` (parent frame, cells)
    dye, dye2  preview colours for the mask's R and G channels
    icon       ship a square <Name>.png + <Name>_m.png icon cut from the south view
    allow_skin pawn sprites: False = visible "skin" pixels fail the checks (coverage gaps)
    ship       False for review-only sprites
    ship_dir   folder under the game's Textures/ the files go to
    expect     calibration: {facing: {"top": px, "front": px}} measured by the checks
    Any VIEWS key (px_per_cell, elev, tilt, outline, light, ...) can be overridden per sprite.
    """

    def __init__(self, name, build, view, canvas, facings=None, variants=None, frames=0, graphic="multi",
                 layer=None, footprint=None, attach=None, pivot=None, dye=(172, 160, 128), dye2=None,
                 icon=False, allow_skin=True, ship=True, ship_dir=None, expect=None, **overrides):
        if view not in VIEWS:
            raise ValueError(f"unknown view {view!r}")
        bad = set(overrides) - set(VIEWS[view])
        if bad:
            raise ValueError(f"{name}: unknown settings {sorted(bad)}")
        self.build = build
        if facings is None:
            facings = ("north",) if graphic == "single" else ("south", "east", "north")
        self.meta = dict(name=name, view=view, canvas=list(canvas), facings=list(facings),
                         variants=list(variants) if variants else None, frames=int(frames), graphic=graphic,
                         layer=layer, footprint=list(footprint) if footprint else None, attach=attach,
                         pivot=list(pivot) if pivot else None, dye=list(dye), dye2=list(dye2) if dye2 else None,
                         icon=icon, allow_skin=allow_skin, ship=ship, ship_dir=ship_dir, expect=expect,
                         **overrides)

    @property
    def name(self):
        return self.meta["name"]


class Ctx:
    """What a build function gets: the variant (body type etc.), the frame index (None for the still) and the
    animation phase t in [0, 1)."""

    def __init__(self, sprite, variant, frame):
        self.sprite = sprite
        self.variant = variant
        self.frame = frame
        n = sprite.meta["frames"]
        self.t = (frame / n) if (frame is not None and n) else 0.0


# ------------------------------------------------------------------ object plumbing

def begin(root):
    """Called by the renderer before each build: new parts hang off `root`, which it turns per facing."""
    PARTS.clear()
    _ROOT[0] = root


def _object(bm, mat, emph=1.0, smooth=False, name="part", mats=None):
    for m in (mats or [mat]):
        if m not in MATERIALS:
            raise KeyError(f"unknown material {m!r} (see spritekit/materials.py)")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = _ROOT[0]
    ob["mats"] = "|".join(mats or [mat])
    ob["emph"] = float(emph)
    ob["smooth"] = bool(smooth)
    PARTS.append(ob)
    return ob


def _bevel(bm, width, angle=35.0, segments=1):
    """Chamfer every edge sharper than `angle` degrees (so cylinder sides and flat seams are left alone)."""
    if width <= 0:
        return
    lim = math.radians(angle)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segments, profile=0.5,
                        affect="EDGES", clamp_overlap=True)


def finalize():
    """Bake modifiers and set normals: flat parts get one normal per face (custom split normals, so a slightly
    non-planar quad still shades as a single facet); smooth parts interpolate, hard only across sharp edges."""
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in PARTS:
        if ob.modifiers:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            ob.data = me
        me = ob.data
        for p in me.polygons:
            p.use_smooth = True
        if ob["smooth"]:
            me.set_sharp_from_angle(angle=math.radians(35))
            continue
        ln = [None] * len(me.loops)
        for p in me.polygons:
            for li in p.loop_indices:
                ln[li] = p.normal[:]
        me.normals_split_custom_set(ln)


# ------------------------------------------------------------------ small helpers

def V(*a):
    return Vector(a[0] if len(a) == 1 else a)


def rot(x=0.0, y=0.0, z=0.0):
    """Rotation matrix from Euler degrees (applied X, then Y, then Z)."""
    return (Matrix.Rotation(math.radians(z), 3, "Z") @ Matrix.Rotation(math.radians(y), 3, "Y")
            @ Matrix.Rotation(math.radians(x), 3, "X"))


def mx(points):
    """Mirror points across x = 0 (the other side of a symmetric part)."""
    return [Vector((-p[0], p[1], p[2])) if len(p) == 3 else (-p[0], p[1]) for p in points]


def linspace(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def lerp(a, b, t):
    return a + (b - a) * t


def spow(x, e):
    return math.copysign(abs(x) ** e, x)


# ------------------------------------------------------------------ solids

def hull(points, mat, bevel=0.0, emph=1.0, name="hull"):
    """Convex hull of explicit 3D points: the workhorse for wedges, chamfered blocks, sloped plates."""
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in points]
    res = bmesh.ops.convex_hull(bm, input=vs)
    kill = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _bevel(bm, bevel)
    return _object(bm, mat, emph, name=name)


def box(center, size, mat, bevel=0.0, r=None, emph=1.0, name="box"):
    """Box of full extents `size` around `center`; r = rot(...) matrix to turn it."""
    c = Vector(center)
    hx, hy, hz = (s / 2 for s in size)
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                v = Vector((sx * hx, sy * hy, sz * hz))
                pts.append(c + (r @ v if r is not None else v))
    return hull(pts, mat, bevel, emph, name)


def frustum(center, bottom, top, height, mat, bevel=0.0, emph=1.0, name="frustum"):
    """Block with a smaller (or larger) top: (w, d) at the bottom, (w, d) at the top, sitting on center.z."""
    c = Vector(center)
    pts = []
    for (w, d), z in ((bottom, 0.0), (top, height)):
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts.append(c + Vector((sx * w / 2, sy * d / 2, z)))
    return hull(pts, mat, bevel, emph, name)


def prism(outline, lo, hi, mat, axis="z", bevel=0.0, emph=1.0, name="prism"):
    """Extrude a 2D outline (may be concave). axis "z": outline in (x, y), from z = lo to hi;
    "y": outline in (x, z), from y = lo to hi; "x": outline in (y, z), from x = lo to hi."""
    def P(a, b, w):
        return {"z": (a, b, w), "y": (a, w, b), "x": (w, a, b)}[axis]
    bm = bmesh.new()
    bot = [bm.verts.new(P(a, b, lo)) for a, b in outline]
    top = [bm.verts.new(P(a, b, hi)) for a, b in outline]
    bm.faces.new(bot)
    bm.faces.new(list(reversed(top)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _bevel(bm, bevel)
    return _object(bm, mat, emph, name=name)


def cyl(p0, p1, r, mat, r1=None, n=12, bevel=0.0, smooth=False, emph=1.0, name="cyl"):
    """Cylinder (or cone with end radius r1) from p0 to p1. n = sides: 8-12 shade in clear bands."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r if r1 is None else r1, depth=d.length)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4(), verts=bm.verts[:])
    _bevel(bm, bevel, angle=50.0)
    return _object(bm, mat, emph, smooth, name)


def ellipsoid(center, radii, mat, segments=16, rings=10, cut_below=None, smooth=False, emph=1.0, name="ellipsoid"):
    """Ellipsoid; cut_below = z offset from the centre where it is sliced flat (a dome: cut_below=0)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    if cut_below is not None:
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, cut_below),
                                     plane_no=(0, 0, 1), clear_inner=True)
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts[:])
    return _object(bm, mat, emph, smooth, name)


def loft(rings, mat, cap_start=True, cap_end=True, mats=None, smooth=False, emph=1.0, name="loft"):
    """Join closed rings of points (all the same length) with quads. mats: optional material per band (gap
    between ring i and i + 1), None = `mat`. Steps, keels and hems belong in the ring shapes, not extra parts."""
    names = [mat] + sorted({m for m in (mats or []) if m and m != mat})
    bm = bmesh.new()
    vr = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(vr[0])
    for i, (a, b) in enumerate(zip(vr, vr[1:])):
        mi = names.index(mats[i]) if mats and i < len(mats) and mats[i] else 0
        for k in range(n):
            try:
                f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            except ValueError:
                continue
            f.material_index = mi
    for flag, ring in ((cap_start, vr[0]), (cap_end, list(reversed(vr[-1])))):
        if flag:
            bm.faces.new(ring)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    return _object(bm, mat, emph, smooth, name, mats=names)


# ------------------------------------------------------------------ surfaces (things wrapped onto a body/head)

class Ellipsoid:
    """Ellipsoid surface. u = azimuth in degrees (0 = front, -Y; +90 = +X), v = elevation in degrees.
    point(u, v, h) is offset h cells along the surface normal."""

    def __init__(self, center, radii):
        self.c, self.r = Vector(center), Vector(radii)

    def _p(self, u, v):
        u, v = math.radians(u), math.radians(max(-89.9, min(89.9, v)))
        cv = math.cos(v)
        return self.c + Vector((self.r.x * cv * math.sin(u), -self.r.y * cv * math.cos(u), self.r.z * math.sin(v)))

    def normal(self, u, v):
        p = self._p(u, v) - self.c
        n = Vector((p.x / self.r.x ** 2, p.y / self.r.y ** 2, p.z / self.r.z ** 2))
        return n.normalized()

    def point(self, u, v, h=0.0):
        return self._p(u, v) + self.normal(u, v) * h

    def outward(self, p):
        return Vector(p) - self.c

    def ring(self, v, h=0.0, n=24, u0=-180.0, u1=180.0):
        if u1 - u0 >= 360.0 - 1e-6:
            return [self.point(u0 + 360.0 * i / n, v, h) for i in range(n)]
        return [self.point(lerp(u0, u1, i / (n - 1)), v, h) for i in range(n)]


def _catmull(xs, ys, x):
    """Smooth interpolation through (xs, ys); xs strictly decreasing (body rows run top to bottom)."""
    if x >= xs[0]:
        return ys[0]
    if x <= xs[-1]:
        return ys[-1]
    i = next(k for k in range(len(xs) - 1) if xs[k] >= x >= xs[k + 1])
    t = (xs[i] - x) / (xs[i] - xs[i + 1])
    p0 = ys[max(i - 1, 0)]
    p1, p2 = ys[i], ys[i + 1]
    p3 = ys[min(i + 2, len(ys) - 1)]
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


# Stand-in pawn body (cells, body canvas centred on the origin). Rows run top (shoulder line) to bottom.
# These are approximations: replace them with silhouettes measured from your own game's body textures
# (alpha width per row in south, depth per row in east) for production work, and never ship those textures.
_ROW_Z = [0.30, 0.25, 0.18, 0.05, -0.12, -0.26, -0.42, -0.55, -0.63, -0.675]
_ROW_A = [0.16, 0.262, 0.300, 0.295, 0.268, 0.250, 0.265, 0.250, 0.185, 0.05]  # half width (south)
_ROW_B = [0.14, 0.190, 0.205, 0.210, 0.200, 0.190, 0.196, 0.184, 0.136, 0.04]  # half depth (east)
_ZONE = [0, 0, 0, 1, 2, 2, 3, 3, 4, 4]       # shoulders, chest, waist, hips, bottom
_TYPES = {
    "Male": dict(a=(1.00, 1.00, 1.00, 1.00, 1.00), b=(1.00, 1.00, 1.00, 1.00, 1.00), belly=0.0, lift=0.0),
    "Female": dict(a=(0.86, 0.88, 0.82, 1.00, 0.96), b=(0.92, 0.96, 0.90, 0.96, 0.96), belly=0.0, lift=-0.01),
    "Thin": dict(a=(0.80, 0.78, 0.78, 0.82, 0.86), b=(0.82, 0.82, 0.82, 0.84, 0.88), belly=0.0, lift=0.0),
    "Hulk": dict(a=(1.36, 1.32, 1.16, 1.10, 1.04), b=(1.30, 1.30, 1.20, 1.14, 1.08), belly=0.0, lift=0.03),
    "Fat": dict(a=(1.12, 1.24, 1.44, 1.38, 1.18), b=(1.20, 1.38, 1.62, 1.46, 1.26), belly=0.05, lift=0.0),
}


SKIN_INSET = 0.012


class Body:
    """Stand-in body for one body type. point(th, z, h): th in degrees around the body (0 = front, +90 = +X,
    180 = back), z in cells (top_z .. bottom_z), h = offset along the surface normal.
    Write garments relative to the anchors (shoulder_z, chest_z, waist_z, hip_z) and the local width/depth, so
    one build function fits all five body types."""

    N = 2.6   # superellipse exponent of the cross-section (boxier than an ellipse)

    def __init__(self, body_type="Male", offset=(0.0, 0.0, 0.0)):
        k = _TYPES[body_type]
        self.type = body_type
        self.off = Vector(offset)
        self.zs = [z + k["lift"] * (1 - i / (len(_ROW_Z) - 1)) for i, z in enumerate(_ROW_Z)]
        self.a = [a * k["a"][_ZONE[i]] for i, a in enumerate(_ROW_A)]
        self.b = [b * k["b"][_ZONE[i]] for i, b in enumerate(_ROW_B)]
        self.yc = [-k["belly"] * math.exp(-((z + 0.14) / 0.17) ** 2) for z in self.zs]
        self.top_z, self.bottom_z = self.zs[0], self.zs[-1]
        self.shoulder_z, self.chest_z = self.zs[2], self.zs[3]
        self.waist_z, self.hip_z = self.zs[5], self.zs[6]

    def width(self, z):
        return _catmull(self.zs, self.a, z)

    def depth(self, z):
        return _catmull(self.zs, self.b, z)

    def _p(self, th, z):
        a, b, yc = self.width(z), self.depth(z), _catmull(self.zs, self.yc, z)
        s, c = math.sin(math.radians(th)), math.cos(math.radians(th))
        e = 2.0 / self.N
        return self.off + Vector((a * spow(s, e), yc - b * spow(c, e), z))

    def outward(self, p):
        p = Vector(p) - self.off
        return Vector((p.x, p.y - _catmull(self.zs, self.yc, p.z), 0.0))

    def normal(self, th, z):
        du = self._p(th + 0.5, z) - self._p(th - 0.5, z)
        dv = self._p(th, z + 0.004) - self._p(th, z - 0.004)
        n = du.cross(dv)
        if n.length < 1e-9:
            return Vector((0, 0, 1 if z > 0 else -1))
        n.normalize()
        return -n if n.dot(self.outward(self._p(th, z))) < 0 else n

    def point(self, th, z, h=0.0):
        return self._p(th, z) + self.normal(th, z) * h

    def ring(self, z, h=0.0, n=28, th0=-180.0, th1=180.0):
        if th1 - th0 >= 360.0 - 1e-6:
            return [self.point(th0 + 360.0 * i / n, z, h) for i in range(n)]
        return [self.point(lerp(th0, th1, i / (n - 1)), z, h) for i in range(n)]

    def mesh(self, mat, rings=24, n=32, h=0.0):
        zs = linspace(self.top_z, self.bottom_z, rings)
        return loft([self.ring(z, h, n) for z in zs], mat, smooth=True, name="body_" + mat)

    def skin(self):
        """The bare body as a cutout: hides apparel parts behind it, and any of it left visible is a gap.
        It sits SKIN_INSET inside the surface so a garment lofted at h >= 0 covers it despite chord sag."""
        return self.mesh("skin", h=-SKIN_INSET)


# Stand-in head, in head-canvas cells (the head canvas sits HEAD_OFFSET above the body canvas).
HEAD_CENTER = (0.0, 0.0, 0.06)
HEAD_RADII = (0.26, 0.25, 0.29)
EYE_Z = -0.07     # eye line on the image, head canvas (eyes at x = +-0.09 in south)


class Head(Ellipsoid):
    def __init__(self):
        super().__init__(HEAD_CENTER, HEAD_RADII)

    def mesh(self, mat):
        return ellipsoid(self.c, self.r, mat, segments=24, rings=14, smooth=True, name="head_" + mat)

    def skin(self):
        return ellipsoid(self.c, self.r - Vector((SKIN_INSET,) * 3), "skin", segments=24, rings=14, smooth=True,
                         name="head_skin")


def eye_z(y, tilt=VIEWS["pawn"]["tilt"]):
    """Model z that lands on the eye line for a surface at depth y: the tilted camera moves a point at depth y
    by y * sin(tilt) on screen, so a visor on the front of a helmet (y = -0.3) needs z = EYE_Z + 0.06."""
    return EYE_Z - y * math.sin(math.radians(tilt))


def body_below_head(body_type="Thin"):
    """For head-layer sprites: the body under the head as an occluder. The game draws the head layer over the
    body, so helmet parts the body would hide (a neck guard behind the shoulders in south) must not reach the
    sprite. The head offset's x part goes along y, so turning the model to east puts the body behind the head."""
    hx, hy = HEAD_OFFSET[body_type]
    return Body(body_type, offset=(0.0, hx, -hy)).mesh("occluder", rings=18, n=24)


def plate(surface, u0, u1, v0, v1, h, thick, mat, grid=(3, 2), outline=None, bevel=0.006, emph=1.0, clear=0.008,
          name="plate"):
    """A solid plate wrapped onto a surface (Body: u = th degrees, v = z cells; Ellipsoid: u, v degrees).
    Few grid divisions = big flat facets (sharp, deliberate); many = a smooth curved plate.
    outline: optional convex polygon in (u, v) the plate is cut to (chevrons, tapers).
    A flat facet is a chord of the curved surface, so its middle dips toward the surface; the plate is lifted
    until every facet keeps `clear` cells above it (so a garment lofted below that height never pokes through)."""
    gu = linspace(u0, u1, grid[0] + 1)
    gv = linspace(v0, v1, grid[1] + 1)
    bm = bmesh.new()
    vs = [[bm.verts.new((u, v, 0.0)) for v in gv] for u in gu]
    for i in range(grid[0]):
        for j in range(grid[1]):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    if outline:
        cu = sum(p[0] for p in outline) / len(outline)
        cv = sum(p[1] for p in outline) / len(outline)
        for k in range(len(outline)):
            a, b = Vector((*outline[k], 0)), Vector((*outline[(k + 1) % len(outline)], 0))
            nrm = Vector((b.y - a.y, a.x - b.x, 0)).normalized()
            if nrm.dot(Vector((cu, cv, 0)) - a) > 0:
                nrm = -nrm
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=a, plane_no=nrm,
                                   clear_outer=True)
    uv = {v: (v.co.x, v.co.y) for v in bm.verts}
    lift = 0.0
    for _ in range(2):
        for v in bm.verts:
            v.co = surface.point(*uv[v], h + lift)
        bm.normal_update()
        flip = [f for f in bm.faces if f.normal.dot(surface.outward(f.calc_center_median())) < 0]
        if flip:
            bmesh.ops.reverse_faces(bm, faces=flip)
            bm.normal_update()
        need = 0.0
        for f in bm.faces:
            cu = sum(uv[v][0] for v in f.verts) / len(f.verts)
            cv = sum(uv[v][1] for v in f.verts) / len(f.verts)
            need = max(need, (surface.point(cu, cv, clear) - f.calc_center_median()).dot(f.normal))
        if need <= 1e-5:
            break
        lift += need
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = _ROOT[0]
    if mat not in MATERIALS:
        raise KeyError(f"unknown material {mat!r}")
    ob["mats"], ob["emph"], ob["smooth"] = mat, float(emph), False
    so = ob.modifiers.new("solid", "SOLIDIFY")
    so.thickness = thick
    so.offset = 1.0
    if bevel > 0:
        bv = ob.modifiers.new("bevel", "BEVEL")
        bv.width = bevel
        bv.segments = 1
        bv.limit_method = "ANGLE"
        bv.angle_limit = math.radians(40)
    PARTS.append(ob)
    return ob


__all__ = ["Sprite", "Ctx", "BODY_TYPES", "V", "rot", "mx", "linspace", "lerp", "hull", "box", "frustum",
           "prism", "cyl", "ellipsoid", "loft", "plate", "Ellipsoid", "Body", "Head", "EYE_Z", "eye_z",
           "body_below_head", "HEAD_CENTER", "HEAD_RADII", "PARTS", "Vector", "Matrix", "math"]
