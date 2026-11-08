# Blender sprite pipeline: game sprites from code

A small, complete pipeline that turns Python code into finished 2D game sprites: apparel worn by pawns,
buildings, vehicles with turrets, and animation frames. The target look and file conventions are RimWorld's
(hand-drawn-looking flat tones, black outlines, dye masks, 3 facings with west mirrored), but the method works for
any game that draws pre-rendered sprites.

Nothing is painted and no AI image generation is involved. A design is a Python file that builds geometry in
Blender from primitives; Blender renders flat data images (which material, which way each surface faces, how far
it is from the camera); numpy turns that data into the final art. Every pixel is reproducible from the source.

```
designs/<key>.py ──► Blender (headless) ──► G-buffers + meta.json ──► numpy shading ──► texture + mask
  geometry code       spritekit/blender_main.py  work/<key>/            spritekit/shade.py   out/<key>/tex/
                                                                              │
                                    review sheet ◄─┘   checks ◄─┘   ship to a mod's Textures/ ◄─┘
                                    out/<key>/sheet.png
```

If you are an agent picking this up: read **Rules for agents** below, run `python pipeline.py selftest`, then
open `designs/rover.py` (vehicle), `designs/relay.py` (building + animation) or `designs/trooper.py` (apparel),
whichever is closest to your task, and copy its structure.

---

## Contents

1. [Rules for agents](#1-rules-for-agents)
2. [Quick start](#2-quick-start)
3. [Folder layout](#3-folder-layout)
4. [Commands](#4-commands)
5. [Coordinates, facings and views](#5-coordinates-facings-and-views)
6. [The G-buffer contract](#6-the-g-buffer-contract)
7. [Writing a design](#7-writing-a-design)
8. [Kit reference](#8-kit-reference)
9. [Materials and the look](#9-materials-and-the-look)
10. [The review loop](#10-the-review-loop)
11. [Checks](#11-checks)
12. [Style rules for RimWorld-looking sprites](#12-style-rules-for-rimworld-looking-sprites)
13. [Shipping to a mod](#13-shipping-to-a-mod)
14. [Extending the pipeline](#14-extending-the-pipeline)
15. [Gotchas (each one cost real time once)](#15-gotchas-each-one-cost-real-time-once)

---

## 1. Rules for agents

1. **Run `python pipeline.py selftest` first** on a new machine or Blender version. It renders shapes with known
   pixel sizes and fails if a camera or the buffer encoding is off.
2. **One design = one file in `designs/`.** Copy the closest demo. Do not edit `spritekit/` to make one design
   work; if the kit really lacks something, add it as a general feature and re-run every demo.
3. **Look at the result after every change.** Open `out/<key>/sheet.png` and `out/<key>/zoom.png` (with your
   image-reading tool). Code that runs is not art that works. Plan on at least two review-and-fix rounds.
4. **Iterate small.** Render one facing and one variant while shaping (`--facings south --variants Male
   --frames none`), then everything once it looks right.
5. **Style changes are re-shades.** Tones, lines, outline and masks live in `spritekit/shade.py` and
   `spritekit/materials.py`; `python pipeline.py shade <key>` re-applies them in seconds without Blender.
6. **`python pipeline.py check <key>` must pass** before you call a design done. A failing check means
   the art is clipped, has a coverage gap, or a mask is wrong, not that the checker is too strict.
7. **Never use AI image generation** anywhere in the chain, and never ship the game's own textures (measure
   them if you need reference data; keep only numbers).
8. Several agents can work at once, one design each: they share the kit read-only and can render on one GPU.
   Whoever coordinates should review every sheet and send concrete revision lists.

## 2. Quick start

Requirements:

- **Blender 4.2 or newer** (written against the 4.2+ API, tested on 5.2). Found automatically from `$BLENDER`,
  then `PATH`, then the usual install folders (Windows `Program Files\Blender Foundation\Blender *`, macOS
  `/Applications/Blender.app`, Linux `/usr/bin`, `/snap/bin`).
- **Python 3.9+** with `numpy`, `scipy`, `Pillow`: `pip install -r requirements.txt`.
- A GPU is optional. The passes are 1 sample each; CPU rendering is about as fast (`SPRITEKIT_CPU=1` forces it).

```bash
pip install -r requirements.txt
python pipeline.py selftest          # calibration: must print "0 failures"
python pipeline.py all mannequin     # the stand-in pawn the apparel previews use (once)
python pipeline.py all trooper       # apparel: body armour x 5 body types + helmet
python pipeline.py all rover         # vehicle: oblique hull + top-down turret
python pipeline.py all relay         # building: 2x2, plus an 8-frame radar animation
```

Each `all` prints where it wrote things; look at `out/<key>/sheet.png`. `examples/` holds the sheets these
commands produce, so you can see what to expect without running anything. Times on a desktop: a few seconds of
Blender and up to ~10 s of shading per design.

## 3. Folder layout

```
pipeline.py               CLI for every stage (system Python)
requirements.txt
spritekit/
  common.py               shared facts: view types, facings, file naming, buffer encodings (plain Python)
  materials.py            material table: colour, dye channel, line group, flags (plain Python)
  kit.py                  geometry builders, stand-in body/head, Sprite declaration (Blender side)
  blender_main.py         Blender entry point: cameras, data passes, render loop, meta.json (Blender side)
  shade.py                buffers -> texture + mask: the look (numpy)
  sheet.py                review sheets, zoom, animation GIFs, icons (numpy/Pillow)
  checks.py               automated checks (numpy/Pillow)
designs/
  calib.py                calibration shapes for selftest
  mannequin.py            stand-in pawn (review underlay, not shipped)
  trooper.py              apparel example
  rover.py                vehicle example
  relay.py                building + animation example
examples/                 review sheets from the demos
work/<key>/               (generated) buffers/, meta.json, blender.log      safe to delete
out/<key>/                (generated) tex/, sheet.png, zoom.png, *.gif     safe to delete
```

Two Pythons are involved and they never import each other's libraries: Blender's bundled Python runs `kit.py`
and `blender_main.py` (bpy, bmesh, mathutils); your system Python runs everything else (numpy, scipy, Pillow).
The only things that cross between them are PNG files and `meta.json`. `common.py` and `materials.py` are plain
Python so both sides can import them.

## 4. Commands

| Command | What it does |
|---|---|
| `python pipeline.py list` | designs and their sprites |
| `python pipeline.py all <key> [filters]` | render + shade + sheet + check |
| `python pipeline.py render <key> [filters]` | Blender only: `work/<key>/buffers/*.png`, `meta.json`, `blender.log` |
| `python pipeline.py shade <key>` | buffers to textures and masks in `out/<key>/tex/` (no Blender) |
| `python pipeline.py sheet <key>` | `out/<key>/sheet.png`, `zoom.png`, `<Sprite>_anim_<facing>.gif` |
| `python pipeline.py check <key>` | automated checks, exit code 1 on failure |
| `python pipeline.py offsets <key>` | per-facing draw offsets of attached sprites (turret positions for vehicle defs) |
| `python pipeline.py ship <key> --to <Textures dir> [--dry-run]` | copy finished files into a mod, with icons |
| `python pipeline.py selftest` | calibration render + checks |
| `python pipeline.py clean <key>` | delete `work/<key>` and `out/<key>` |

Filters for `render` and `all`: `--only Sprite1,Sprite2`, `--facings south,east`, `--variants Male,Hulk`,
`--frames none` (still only) or `--frames 0,4`. Partial renders merge into the existing buffers and meta.

## 5. Coordinates, facings and views

**Units are cells everywhere: 1 Blender unit = 1 map cell.** Axes: **+X = the model's left side** (screen right
in the south view), **-Y = the model's front**, +Z up. Buildings and vehicles stand on z = 0 with the footprint
centred on the origin. Pawn sprites are centred on the canvas centre.

**Facings.** The model is built once and turned for each facing; the facing name is where its front points on
screen. The game mirrors east to get west, so west is never rendered.

| Facing | Model turned | Front points |
|---|---|---|
| south | 0° | toward the viewer (down the image) |
| east | +90° | right |
| north | 180° | away (up the image) |

**The image centre is always the model origin**, in every facing. That is what lets the game draw every facing
at the same position without per-facing offsets.

**View types** (`spritekit/common.py`, `VIEWS`; any value can be overridden per sprite):

| View | Camera | Density | Use |
|---|---|---|---|
| `pawn` | orthographic, tilted 12° down; the model is stretched 1/cos(12°) vertically so heights stay true | 341.33 px/cell (a 1.5-cell canvas is 512 px) | apparel, anything worn |
| `oblique` | orthographic at `elev` (60°) above the ground, rendered with wide pixels so the ground keeps its full length and vertical faces show at cot(elev) = 0.577 of their height | 128 px/cell | buildings, vehicle hulls |
| `topdown` | straight down, north (+Y) up the image | 128 px/cell | turrets, roofs, anything that rotates freely |

Calibration (what `selftest` measures): in `oblique` a 1-cell cube shows a 128 px top and a 74 px front; in
`topdown` a 2-cell bar is 256 px; in `pawn` a 0.5-cell cube shows a 171 px front and a 35 px top.

**The oblique trick.** An orthographic camera at elevation E shortens ground lengths to sin(E). Setting
`pixel_aspect_x = 1 / sin(E)` (with `sensor_fit = HORIZONTAL` and `ortho_scale = canvas width`) stretches the
image vertically by exactly that much, so the ground is undistorted and a height h appears as h·cot(E). This is
the projection vehicle and building mods for RimWorld use.

**The pawn view.** The 12° tilt shows a little of the top of things. Because of it, a point at depth y moves
y·sin(12°) on screen, so something on the front of a helmet (y ≈ -0.3) lands 0.06 cells lower than its z.
`eye_z(y)` corrects for that when you place visors and eye slits.

- The body canvas and the head canvas are both 1.5 cells. The game draws the head canvas at the body type's
  head offset (`common.HEAD_OFFSET`, e.g. Male (0.04, 0.34): 0.34 up in every facing, 0.04 sideways in east/west
  only). Approximate vanilla values; check `BodyTypeDef.headOffset` in your game version.
- Draw order is body, body apparel, head, headgear. So the head hides the upper chest in south and north, and
  the head layer is drawn over the body even where the 3D helmet would be behind it.
- `EYE_Z = -0.07` (head canvas) is where the game draws eyes.

## 6. The G-buffer contract

Blender does no lighting and no shading. Every material is an emission shader whose colour *is* data, and each
facing is rendered three times, swapping the material output between passes:

| Pass | File | Encoding |
|---|---|---|
| id | `<stem>_id.png` | R = (material index + 1) × 8, G = emph × 100, A = coverage |
| normal | `<stem>_normal.png` | world-space normal × 0.5 + 0.5, flipped toward the camera on back faces |
| depth | `<stem>_depth.png` | distance toward the camera, v = (d + range) / (2·range) × 255; R = floor(v), G = frac(v) × 255 |

Render settings and why each matters (all in `blender_main.reset()`):

- **Cycles, 1 sample, `filter_width = 0.01`, no denoise, 0 bounces**: each pixel is one ray through its centre,
  so it carries one surface's exact values, never a blend. Anti-aliasing comes from rendering 3× larger
  (`ss`) and box-filtering down in numpy.
- **View transform `Raw`, look None, exposure 0, gamma 1**: any display transform (Standard, AgX, Filmic) changes
  the numbers. `shade.decode()` refuses buffers whose ids are not multiples of 8, which catches this.
- **`dither_intensity = 0`**: dither noise corrupts packed normals and depth (grainy surfaces).
- **8-bit PNG, film transparent**: Pillow reads 8-bit RGBA exactly; it does not read 16-bit RGB PNGs faithfully,
  which is why depth is packed into two bytes instead.
- **World-space normals, not camera-space**: with the tilted pawn camera, every vertical face would otherwise count
  as facing slightly down and lose a tone step.
- **Flat faces get custom split normals** (one normal per polygon), so a slightly non-planar quad still shades as
  one facet instead of splitting into two triangles of different tones.
- **`use_persistent_data`**: geometry stays loaded between the three passes; only the shader link changes.

`meta.json` records every sprite's declaration (view, canvas, facings, variants, frames, naming, dye, pivot...),
the Blender version and the material order. The numpy side reads only the PNGs and this file.

## 7. Writing a design

A design module lists its outputs in `SPRITES` and builds geometry in plain functions:

```python
from spritekit.kit import Sprite, box, cyl, hull


def crate(ctx):
    hull([(x, y, z) for x in (-0.42, 0.42) for y in (-0.42, 0.42) for z in (0.0, 0.62)]
         + [(x, y, 0.70) for x in (-0.36, 0.36) for y in (-0.36, 0.36)], "paint", bevel=0.02, emph=1.6)
    box((0, -0.43, 0.32), (0.5, 0.03, 0.10), "hazard")
    cyl((0.25, -0.2, 0.70), (0.25, -0.2, 0.76), 0.08, "steel", n=10, bevel=0.01)


SPRITES = [
    Sprite("SupplyCrate", crate, "oblique", canvas=(2, 2), footprint=(1, 1),
           ship_dir="Things/Building/SupplyCrate"),
]
```

Save it as `designs/crate.py` and run `python pipeline.py all crate`.

**`Sprite(name, build, view, canvas, ...)`**

| Field | Meaning |
|---|---|
| `name` | file name stem, CamelCase, unique in the game's texture folder |
| `build` | `function(ctx)` that builds the geometry |
| `view` | `"pawn"`, `"oblique"` or `"topdown"` |
| `canvas` | (w, h) in cells; the image centre is the model origin. Becomes `drawSize` in the def |
| `facings` | default south/east/north (`["north"]` for `graphic="single"`) |
| `variants` | e.g. `BODY_TYPES`; each is a separate build with `ctx.variant` set, files get `_<Variant>` |
| `frames` | number of animation frames rendered as well as the still; `ctx.t` runs 0 .. (n-1)/n |
| `graphic` | `"multi"`: one texture per facing; `"single"`: one texture (`<Name>.png` + `<Name>_m.png`) |
| `layer` | pawn sprites: `"body"` or `"head"` (head sprites sit at the head offset in previews and checks) |
| `footprint` | (w, h) cells, drawn as a grid in the sheet |
| `attach`, `pivot` | draw this sprite on another one (turret on hull) at `pivot` (parent frame, cells) |
| `dye`, `dye2` | preview colours for mask R and G |
| `icon` | ship a square `<Name>.png` + `<Name>_m.png` icon cut from the south view |
| `allow_skin` | pawn sprites: `False` makes visible stand-in skin a check failure |
| `ship`, `ship_dir` | whether and where (under `Textures/`) `ship` copies the files |
| `expect` | calibration measurements (see `designs/calib.py`) |
| any `VIEWS` key | per-sprite override: `px_per_cell`, `elev`, `tilt`, `outline`, `light`, `face_on`, `depth_range`, `ss` |

**`ctx`**: `ctx.variant` (body type etc. or None), `ctx.frame` (None for the still), `ctx.t` (0..1 phase),
`ctx.sprite`.

Patterns by asset type (each demo's docstring explains its choices):

- **Apparel** (`trooper.py`): `b = Body(ctx.variant)`, `b.skin()` first, then garments placed from the body's
  anchors (`shoulder_z`, `chest_z`, `waist_z`, `hip_z`) and local `width(z)`; rigid parts scale with
  `b.width(b.chest_z) / 0.265`. One function serves all five body types. Helmets: `Head().skin()`,
  `body_below_head()`, then the shell built on an `Ellipsoid` just outside the head.
- **Vehicle** (`rover.py`): one main `hull()` body with a sloped front and sides, wheels/fenders/lamps tucked
  into it; the turret ring is hull art; the turret is a separate `topdown` sprite, built around its pivot at the
  origin with its front at -Y, attached with `attach=` and `pivot=`.
- **Building** (`relay.py`): plinth on z = 0 covering the footprint, tapered blocks on it; stuff-coloured parts in
  `paint`; canvas tall enough for the tallest part in every facing.
- **Animation** (`relay.py`): read `ctx.frame` / `ctx.t` and move only the animated part; everything else must
  build identically in every frame. Frames ship to a `Frames/` subfolder.

## 8. Kit reference

All in `spritekit/kit.py`. Every builder takes `mat` (a name from `materials.py`) and `emph` (1 = ordinary part,
up to 2 = identity part that may show two tone steps), and returns the Blender object.

**Solids** (prefer these; few bold planes are the look):

| Builder | Use |
|---|---|
| `hull(points, mat, bevel=0)` | convex hull of explicit 3D points: wedges, chamfered blocks, sloped hulls, reflectors. The workhorse |
| `box(center, size, mat, bevel=0, r=None)` | box of full extents `size`; `r=rot(z=30)` turns it |
| `frustum(center, (w, d), (w_top, d_top), height, mat)` | tapered block standing on `center.z` |
| `prism(outline, lo, hi, mat, axis="z")` | extrude a 2D outline (may be concave) along z, y or x |
| `cyl(p0, p1, r, mat, r1=None, n=12)` | cylinder or cone between two points; 8-12 sides shade in clean bands |
| `ellipsoid(center, radii, mat, cut_below=None)` | ellipsoid, or a dome when sliced (`cut_below` = z offset from its centre) |
| `loft(rings, mat, mats=None)` | join closed rings of points: one continuous shell; per-band materials with `mats` |

`bevel` chamfers only edges sharper than 35° (50° on cylinders), so flat seams and cylinder sides stay clean.

**Surfaces** for things that wrap around a body or head:

| Item | Meaning |
|---|---|
| `Body(body_type)` | stand-in body. `point(th, z, h)`: th in degrees around it (0 front, +90 = +X, 180 back), z in cells, h offset along the normal. `ring(z, h, n)`, `width(z)`, `depth(z)`, `normal(th, z)`, anchors `top_z shoulder_z chest_z waist_z hip_z bottom_z`, `skin()`, `mesh(mat)` |
| `Head()` | stand-in head (an `Ellipsoid` at `HEAD_CENTER`, `HEAD_RADII`); `skin()`, `mesh(mat)` |
| `Ellipsoid(center, radii)` | `point(u, v, h)`: u azimuth (0 front, +90 = +X), v elevation, degrees |
| `plate(surface, u0, u1, v0, v1, h, thick, mat, grid=(3, 2), outline=None)` | a solid plate wrapped onto a surface. Few grid divisions = big flat facets. `outline` = convex polygon in (u, v) to cut it to (chevrons, tapers). Lifts itself so no facet dips below `clear` (chords of a curved surface sag into it) |
| `body_below_head(body_type="Thin")` | the body under a helmet as an occluder: parts behind the neck disappear like they would in game |
| `eye_z(y)`, `EYE_Z` | z that lands on the game's eye line for a surface at depth y |
| `BODY_TYPES` | `["Male", "Female", "Thin", "Hulk", "Fat"]` |

**Helpers**: `V(x, y, z)` (a Vector), `rot(x, y, z)` (rotation matrix from degrees), `mx(points)` (mirror across
x = 0), `linspace`, `lerp`, plus `Vector`, `Matrix`, `math`.

The stand-in body and head are approximations. For production apparel, replace the `_ROW_*` tables in `kit.py`
with silhouettes measured from your own game's body textures (opaque width per row in south, depth per row in
east), keep only the numbers, and never ship the textures.

## 9. Materials and the look

`spritekit/materials.py` is the material table. Each entry: `rgb` (face-on colour), `mask` (0 = dyed by the
first colour, mask R; 1 = second colour, mask G; None = keeps its colour), `group` (a seam line is drawn where
groups meet), and optional flags `unlit` (lamps), `cutout` (stand-in body: hides what is behind it, never drawn),
`pattern="hazard"` (diagonal stripes in screen space).

| Material | For |
|---|---|
| `paint`, `paint2`, `stripe` | dyed plates (near-white so the dye comes through), secondary plates, second-colour stripes |
| `concrete`, `frame`, `steel`, `dark`, `rubber` | undyed structure, gunmetal frames, bright metal, openings and slots, tyres |
| `cloth`, `canvas`, `leather`, `glass` | fabric, bags, straps, windows |
| `hazard`, `lamp`, `lamp_red` | yellow-black stripes, unlit lights |
| `flesh`, `skin`, `occluder` | stand-in pawn (visible), stand-in pawn as cutout (gaps counted), cutout (not counted) |

Add new materials at the **end** of the table (the index is the id; there is room for 31).

**How a pixel gets its colour** (`spritekit/shade.py`):

1. **Tone**: the material's face-on colour, stepped by how far the surface normal turns toward or away from the
   light compared with a face-on surface (`face_on`: up for oblique/topdown, toward the camera for pawn).
   One step per `STEP` (0.22) of n·L, multiplier from `TONES` (0.64 / 0.80 / 1.0 / 1.10 / 1.18), clamped to
   ±1 step for ordinary parts and ±2 for `emph > 1`. Flat, but solid.
2. **Lines**: a dark line (`INK_STEP`) on the far side of every depth step (where one part stands in front of
   another, width `LINE_STEP` cells) and a thinner seam (`INK_SEAM`) where material groups meet.
3. **Outline**: near-black, `outline` cells wide (0.032-0.035, i.e. ~4 px at 128 px/cell, 12 px at 512 px),
   drawn outside the silhouette.
4. **Mask**: R where the material is dyed by the first colour, G for the second; black elsewhere and in the
   outline.
5. **Downsample** from the 3× render with premultiplied alpha.

No cast shadows, no ambient occlusion, no speculars, no noise: those read as "rendered", not drawn. To change
the look, edit these constants or the function and run `shade`; to change one material, edit its entry.

## 10. The review loop

1. Shape on one facing and one variant: `python pipeline.py all <key> --facings south --variants Male --frames none`.
   (Checks will report the facings you skipped as missing; that is expected mid-iteration.)
2. Read `out/<key>/zoom.png` for detail (south and east, enlarged) and `out/<key>/sheet.png` for the whole set
   (plain and dyed, S / E / N / W, every variant, turrets on hulls, apparel on the stand-in pawn, frames).
3. Fix, re-render. When south looks right, render everything and review all facings together.
4. Run `check`. Then judge against this list:
   - Does the silhouette alone say what it is? Is it more than a rounded box?
   - Do the important parts read at 1:1? Anything under ~3 px at 128 px/cell turns into noise.
   - Is the same object in every facing (a pack seen in north also exists in east)?
   - Does the dyed row still read (values carry the form, not hue)?
   - Any accidental face (two dark dots side by side read as eyes)?
   - Apparel: on all five bodies, nothing clipping through, identity visible below the head?

Budget two full review rounds. The demos needed them: the first trooper had bare skin showing at the shoulders
(chord sag, now handled by the kit), a buried vent that left two dots reading as a face, and ear cups sunk into the
helmet; the first relay's antenna left the canvas in some frames and two roof boxes read as eyes.

## 11. Checks

`python pipeline.py check <key>` (also the last step of `all`):

| Check | Fails when | Fix |
|---|---|---|
| present | texture or mask missing | render + shade that sprite / facing / frame |
| size | image is not canvas × px_per_cell | do not resize outputs by hand |
| edge | anything non-transparent in the outer 2 px | enlarge `canvas` or bring parts in: Blender clips silently |
| mask | mask set where the texture is transparent | a shading bug; report it |
| skin | stand-in skin visible on a pawn sprite with `allow_skin=False` (outside what the head layer covers) | cover the gap; usually a plate edge, a missing band or a too-small helmet |
| calibration | a measurement in `expect` off by more than 2 px | camera or projection settings changed |

Warnings note sprites with nothing dyeable and skin checks run without the stand-in head (render `mannequin`).

## 12. Style rules for RimWorld-looking sprites

Learned over many designs; each was a real review comment at some point.

**Everything**

- Few, large, deliberate planes. Chamfers, tapers and steps in the outline; never a plain box silhouette.
- Values carry the form: near-white dyed plates, mid-grey secondary plates and frames, dark gaps. Neighbouring
  regions need at least ~20/255 of value difference or they merge in game.
- Chunky detail. Anything thinner than ~0.025 cells (3 px at 128 px/cell) disappears or flickers: enlarge it,
  merge it into a bigger shape, or delete it. No thin rods, wires or antennas.
- No symmetric pairs of small dark or light dots (vents, lamps, bolts) on a flat face: they read as eyes.
- One accent colour (a lamp, a beacon) at most, and never on a pawn's face.
- No part may clip visibly through another or float off the body. Tuck parts in.
- Every facing shows the same object; parts only vanish where the body or head truly hides them.

**Apparel**

- The head hides the upper chest in south and north: put the identity in the shoulders (out past the head),
  waist, belt, hips and back.
- Shoulders: low, rounded caps that hug the arm. No spikes, no stacked or flared pauldrons.
- One build function for all body types, written relative to body anchors; check Fat and Hulk every round.
- Helmets: real volume, compact (barely larger than the head, or they hide the design), a designed outline in
  south, the face projecting and the back of the skull a rounded mass in east, the visor or slit on the eye line
  (`eye_z`), full coverage of the head, nothing behind the neck (`body_below_head`).
- Visors are plain dark bands or slots; no glowing eyes.

**Vehicles**

- One continuous body, not boxes on a tray. Wheels, fenders, lamps tucked into it.
- Hull and turret are separate: the turret is top-down, points north, centred on its pivot; the turret ring stays
  in the hull art so the turret never shows an empty socket when it turns.
- Canvas big enough for every facing; the image centre is the footprint centre.

**Buildings**

- A plinth or base that covers the footprint, so the building sits on its cells.
- Stuff-coloured parts are `paint` (the game tints mask R with the material colour).
- Canvas = `drawSize`; tall parts need a taller canvas, not an offset.

## 13. Shipping to a mod

`python pipeline.py ship <key> --to <ModFolder>/Textures` copies every shipped sprite to `Textures/<ship_dir>/`
(frames to `Frames/` under it) and writes icons for `icon=True` sprites. Use `--dry-run` first.

**File naming** (RimWorld's loaders):

| Sprite | Files |
|---|---|
| `graphic="multi"` (buildings, hulls, headgear) | `<Name>_south.png`, `_east`, `_north` + masks `<Name>_southm.png` ... |
| apparel with `variants=BODY_TYPES` | `<Name>_<BodyType>_<facing>.png` + `<Name>_<BodyType>_<facing>m.png` |
| `graphic="single"` (turrets, items) | `<Name>.png` + `<Name>_m.png` |
| icon | `<Name>.png` + `<Name>_m.png` beside the worn textures |
| frames | `Frames/<Name>_fNN_<facing>.png` (+ masks) |

West is the game mirroring east (Graphic_Multi does this when there is no west texture).

**Apparel def** (graphic parts only). Body-layer apparel (OnSkin/Middle/Shell) looks up
`<wornGraphicPath>_<BodyType>_<facing>`; headgear (Overhead/EyeCover) and packs look up
`<wornGraphicPath>_<facing>`. `useWornGraphicMask` makes the worn graphic use the mask (CutoutComplex).

```xml
<graphicData>
  <texPath>Things/Apparel/Trooper/TrooperArmor/TrooperArmor</texPath>   <!-- the icon -->
  <graphicClass>Graphic_Single</graphicClass>
  <shaderType>CutoutComplex</shaderType>
</graphicData>
<apparel>
  <wornGraphicPath>Things/Apparel/Trooper/TrooperArmor/TrooperArmor</wornGraphicPath>
  <useWornGraphicMask>true</useWornGraphicMask>
  <layers><li>Shell</li></layers>
</apparel>
```

**Building def**:

```xml
<size>(2,2)</size>
<graphicData>
  <texPath>Things/Building/Relay/Relay</texPath>
  <graphicClass>Graphic_Multi</graphicClass>
  <shaderType>CutoutComplex</shaderType>
  <drawSize>(3,4)</drawSize>                                  <!-- = the sprite's canvas -->
</graphicData>
```

**Vehicles** depend on the vehicle framework you use. The usual contract, which this pipeline produces: hull
textures per facing with `<tex>_<facing>m.png` masks, drawn centred on the vehicle; the turret as a single
top-down texture pointing north with `<tex>_m.png`, drawn at a per-facing offset from the hull centre.
`python pipeline.py offsets <key>` prints those offsets (cells, x right, y up) for every attached sprite.
`drawSize` is the canvas in cells.

**Masks**: CutoutComplex multiplies mask R by the first colour (stuff colour, dye) and G by the second. Some
vehicle frameworks read only R; keep `stripe` (G) off sprites for those.

## 14. Extending the pipeline

- **New material**: append to `MATERIALS`; pick `rgb`, `mask`, `group`. Re-shade.
- **New look**: edit `shade.py` (constants first). Buffers stay valid; only `shade` reruns.
- **New view type**: add it to `common.VIEWS` (density, light, face-on normal, outline, depth range) and a camera
  branch to `blender_main.setup_camera()`; add a calibration shape to `designs/calib.py` with `expect`.
- **Surface detail** (cloth weave, concrete pits): add a fourth pass driven by each object's own coordinates (so a
  part looks the same in every scene and facing) and multiply it in `shade.py`. Keep it faint.
- **Walk cycles**: keep leg geometry in joint tables, pose them per frame from `ctx.t` (stance/swing foot paths,
  two-bone IK that keeps segment lengths), keep everything else identical, and check the reach of every frame
  against the canvas. Ship frames apart from the still so the game's hull loader never picks them up.
- **Connecting pieces** (walls that join neighbours): render each piece with its real neighbours in the scene, in
  every connection state, then cut each cell's tile out of the render (a screen column for north/south pieces).
  Shading and outlines are computed on the whole render before cutting, so tiles match at every seam. Pack the
  tiles into an atlas and generate the lookup table the game code reads.
- **Matching a reference picture**: add a perspective camera at a chosen azimuth/elevation, shade the result the
  same way and paste it next to the reference.
- **Parallel renders**: run several `render` commands with disjoint `--only` / `--variants` filters (they merge
  into one meta.json; run them into separate copies or sequentially if you see races on meta.json).

## 15. Gotchas (each one cost real time once)

- **Blender exits 0 when the script raises** unless you pass `--python-exit-code 1`. `pipeline.py` passes it and
  also scans the log for `Traceback`.
- **`--factory-startup`** keeps user preferences and add-ons out of the render.
- **Colour management silently alters data passes.** View transform must be `Raw`; `decode()` checks it.
- **Dither must be 0** for packed 8-bit data.
- **Blender clips at the canvas without warning.** The edge check exists for this; a turning part (antenna,
  barrel) may only leave the canvas in some frames or facings.
- **Flat facets are chords**: a big flat facet over a curved body dips below the surface in its middle, and
  whatever is underneath pokes through. `plate()` lifts itself to clear; the stand-in skin sits `SKIN_INSET`
  inside the surface. Lofts over lofts need the same care (offset the outer one more).
- **Convex hulls** leave interior vertices and triangulated flat faces; `hull()` deletes the former and dissolves
  the latter so bevels do not chamfer flat seams.
- **Open meshes** show their back faces; the normal pass flips them toward the camera, but closed solids are safer.
- **Materials in Blender 4.x** need `use_nodes = True`; in 5.x node trees always exist. The kit handles both.
- **GPU first run** may spend a minute compiling kernels. CPU is fine for 1-sample passes (`SPRITEKIT_CPU=1`).
- **Pillow and 16-bit PNGs**: 16-bit RGB is read as 8-bit. Keep buffers 8-bit and pack wide values.
- **Two Pythons**: Blender's bundled Python has no scipy or Pillow; your Python has no bpy. Keep `common.py` and
  `materials.py` free of both, and pass everything else through PNGs and meta.json.
- **Render metadata**: Blender stamps date and render time into the buffer PNGs. Buffers live in `work/` and are
  never shipped; textures, sheets and icons are written by Pillow without metadata.
