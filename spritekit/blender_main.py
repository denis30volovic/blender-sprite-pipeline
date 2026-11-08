"""Blender side of the pipeline: build each sprite's geometry and render its G-buffers.

    blender -b --factory-startup --python-exit-code 1 --python spritekit/blender_main.py -- \
        <design> <work_dir> [--only A,B] [--facings south,east] [--variants Male] [--frames none|0,3]

pipeline.py runs this for you. Per sprite, (variant, frame) and facing it writes three flat 8-bit passes to
<work_dir>/buffers/<stem>_{id,normal,depth}.png and merges the sprite declarations into <work_dir>/meta.json:

  id      R = (material index + 1) * 8, G = emph * 100, A = coverage
  normal  world-space normal * 0.5 + 0.5 (flipped toward the camera on back faces)
  depth   distance toward the camera, packed in two bytes: v = (d + range) / (2 range) * 255, R = floor(v),
          G = frac(v) * 255

No lights, no shading: every material is an emission shader whose colour is the data, rendered with 1 sample,
a tiny pixel filter, no dithering and the Raw view transform, so the PNG holds the exact values.
"""
import argparse
import importlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from spritekit import common, kit  # noqa: E402
from spritekit.materials import NAMES  # noqa: E402

_GPU = []


def use_gpu():
    if _GPU:
        return _GPU[0]
    ok = False
    if not os.environ.get("SPRITEKIT_CPU"):
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for t in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
                try:
                    prefs.compute_device_type = t
                except TypeError:
                    continue
                prefs.get_devices()
                if any(d.type != "CPU" for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type != "CPU"
                    ok = True
                    break
        except Exception as e:  # noqa: BLE001
            print("gpu setup failed, using CPU:", e)
    _GPU.append(ok)
    return ok


def reset():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for x in list(coll):
            coll.remove(x)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU" if use_gpu() else "CPU"
    sc.cycles.samples = 1
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.filter_width = 0.01
    sc.render.film_transparent = True
    sc.render.use_persistent_data = True
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    sc.render.dither_intensity = 0.0
    for attr in ("use_compositing", "use_sequencer"):
        if hasattr(sc.render, attr):
            setattr(sc.render, attr, False)
    im = sc.render.image_settings
    im.file_format, im.color_mode, im.color_depth = "PNG", "RGBA", "8"
    sc.view_settings.view_transform = "Raw"      # data, not colour: no display transform may touch it
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0


def setup_camera(sprite, v):
    """Camera, root and pivot for the sprite's view. Returns (pivot, toward): the pivot is turned per facing,
    `toward` is the unit vector from the scene to the camera (the depth pass measures along it)."""
    sc = bpy.context.scene
    view = sprite["view"]
    W, H = sprite["canvas"]
    ss, ppc = v["ss"], v["px_per_cell"]
    sc.render.resolution_x = int(round(W * ppc * ss))
    sc.render.resolution_y = int(round(H * ppc * ss))
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL"
    cd.ortho_scale = W
    cd.clip_start, cd.clip_end = 0.01, 1000.0
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    root = bpy.data.objects.new("root", None)
    sc.collection.objects.link(root)
    if view == "pawn":
        t = math.radians(v["tilt"])
        toward = Vector((0.0, -math.cos(t), math.sin(t)))
        cam.rotation_euler = (math.pi / 2 - t, 0.0, 0.0)
        root.scale = (1.0, 1.0, 1.0 / math.cos(t))      # heights stay true on the image
    elif view == "oblique":
        e = math.radians(v["elev"])
        toward = Vector((0.0, -math.cos(e), math.sin(e)))
        cam.rotation_euler = (math.pi / 2 - e, 0.0, 0.0)
        # wide pixels: the image keeps ground length 1:1, vertical faces show at cot(elev) of their height
        sc.render.pixel_aspect_x = 1.0 / math.sin(e)
    else:
        toward = Vector((0.0, 0.0, 1.0))
        cam.rotation_euler = (0.0, 0.0, 0.0)
    cam.location = toward * 100.0
    pivot = bpy.data.objects.new("pivot", None)
    sc.collection.objects.link(pivot)
    pivot.parent = root
    return pivot, toward


_PASS_MATS = []


def pass_material(name, emph, toward, rng):
    m = bpy.data.materials.new(f"{name}@{emph:.2f}")
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial")
    out.name = "OUT"

    def emission(key):
        e = N("ShaderNodeEmission")
        e.name = "E_" + key
        e.inputs["Strength"].default_value = 1.0
        return e

    idx = NAMES.index(name)
    emission("id").inputs["Color"].default_value = (
        (idx + 1) * common.ID_STEP / 255.0, min(emph * common.EMPH_SCALE, 255.0) / 255.0, 0.0, 1.0)

    geo = N("ShaderNodeNewGeometry")
    flip = N("ShaderNodeMath")
    flip.operation = "MULTIPLY_ADD"
    L(geo.outputs["Backfacing"], flip.inputs[0])
    flip.inputs[1].default_value = -2.0
    flip.inputs[2].default_value = 1.0
    sc_n = N("ShaderNodeVectorMath")
    sc_n.operation = "SCALE"
    L(geo.outputs["Normal"], sc_n.inputs[0])
    L(flip.outputs[0], sc_n.inputs["Scale"])
    enc = N("ShaderNodeVectorMath")
    enc.operation = "MULTIPLY_ADD"
    L(sc_n.outputs["Vector"], enc.inputs[0])
    enc.inputs[1].default_value = (0.5, 0.5, 0.5)
    enc.inputs[2].default_value = (0.5, 0.5, 0.5)
    L(enc.outputs["Vector"], emission("normal").inputs["Color"])

    dot = N("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L(geo.outputs["Position"], dot.inputs[0])
    dot.inputs[1].default_value = toward

    def math_node(op, a, b=None, clamp=False):
        n = N("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    u = math_node("MULTIPLY", math_node("ADD", dot.outputs["Value"], rng), 1.0 / (2.0 * rng), clamp=True)
    val = math_node("MULTIPLY", u, 254.999)
    hi = math_node("FLOOR", val)
    cc = N("ShaderNodeCombineColor")
    L(math_node("DIVIDE", hi, 255.0), cc.inputs[0])
    L(math_node("SUBTRACT", val, hi), cc.inputs[1])
    L(cc.outputs["Color"], emission("depth").inputs["Color"])
    _PASS_MATS.append(m)
    return m


def assign_materials(toward, rng):
    _PASS_MATS.clear()
    cache = {}
    for ob in kit.PARTS:
        emph = round(float(ob["emph"]), 2)
        me = ob.data
        idxs = [p.material_index for p in me.polygons]
        me.materials.clear()
        for name in ob["mats"].split("|"):
            key = (name, emph)
            if key not in cache:
                cache[key] = pass_material(name, emph, toward, rng)
            me.materials.append(cache[key])
        me.polygons.foreach_set("material_index", idxs)


def set_pass(key):
    for m in _PASS_MATS:
        nt = m.node_tree
        nt.links.new(nt.nodes["E_" + key].outputs[0], nt.nodes["OUT"].inputs["Surface"])


def render_job(sprite_obj, variant, frame, facings, buf_dir):
    s = sprite_obj.meta
    v = common.view_settings(s)
    reset()
    pivot, toward = setup_camera(s, v)
    kit.begin(pivot)
    sprite_obj.build(kit.Ctx(sprite_obj, variant, frame))
    kit.finalize()
    assign_materials(toward, v["depth_range"])
    sc = bpy.context.scene
    for facing in facings:
        pivot.rotation_euler = (0.0, 0.0, math.radians(common.FACING_YAW[facing]))
        t0 = time.time()
        stem = common.stem(s, facing, variant, frame)
        for key in common.PASSES:
            set_pass(key)
            sc.render.filepath = os.path.join(buf_dir, f"{stem}_{key}.png")
            bpy.ops.render.render(write_still=True)
        print(f"RENDER {stem} {time.time() - t0:.2f}s", flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser(prog="blender_main.py")
    ap.add_argument("design")
    ap.add_argument("work")
    ap.add_argument("--only")
    ap.add_argument("--facings")
    ap.add_argument("--variants")
    ap.add_argument("--frames")
    a = ap.parse_args(argv)
    design = importlib.import_module(f"designs.{a.design}")
    work = os.path.abspath(a.work)
    buf_dir = os.path.join(work, "buffers")
    os.makedirs(buf_dir, exist_ok=True)
    print("device:", "GPU" if use_gpu() else "CPU", "| blender", bpy.app.version_string, flush=True)
    meta_p = os.path.join(work, "meta.json")
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {"sprites": {}}
    meta.update(design=a.design, blender=bpy.app.version_string, materials=NAMES)
    only = set(a.only.split(",")) if a.only else None
    for sp in design.SPRITES:
        meta["sprites"][sp.name] = sp.meta
        if only and sp.name not in only:
            continue
        facings = [f for f in sp.meta["facings"] if not a.facings or f in a.facings.split(",")]
        for variant, frame in common.jobs(sp.meta):
            if a.variants and variant and variant not in a.variants.split(","):
                continue
            if frame is not None and a.frames:
                if a.frames == "none" or str(frame) not in a.frames.split(","):
                    continue
            render_job(sp, variant, frame, facings, buf_dir)
    meta["sprites"] = {sp.name: meta["sprites"][sp.name] for sp in design.SPRITES}
    json.dump(meta, open(meta_p, "w"), indent=1)


main()
