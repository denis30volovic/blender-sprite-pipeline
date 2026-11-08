"""Code-to-sprite pipeline: Blender builds and renders G-buffers, numpy shades them, then review, check, ship.

    python pipeline.py list
    python pipeline.py all <design> [filters]     render + shade + sheet + check
    python pipeline.py render <design> [filters]  Blender only -> work/<design>/buffers, meta.json
    python pipeline.py shade <design>             buffers -> out/<design>/tex (no Blender; seconds)
    python pipeline.py sheet <design>             out/<design>/sheet.png, zoom.png, *_anim_*.gif
    python pipeline.py check <design>             automated checks (exit code 1 on failure)
    python pipeline.py ship <design> --to <Textures dir> [--dry-run]
    python pipeline.py offsets <design>           per-facing draw offsets of attached sprites (turrets)
    python pipeline.py selftest                   calibration: camera projections and buffer decoding
    python pipeline.py clean <design>             delete work/<design> and out/<design>

Filters (render/all): --only Sprite1,Sprite2  --facings south,east  --variants Male  --frames none|0,4
Blender is found from $BLENDER, then PATH, then the usual install folders.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from spritekit import common  # noqa: E402

WORK = os.path.join(HERE, "work")
OUT = os.path.join(HERE, "out")


def find_blender():
    env = os.environ.get("BLENDER")
    if env and os.path.exists(env):
        return env
    exe = shutil.which("blender")
    if exe:
        return exe
    pats = [r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender",
            os.path.expanduser("~/blender*/blender")]
    found = [p for pat in pats for p in glob.glob(pat)]

    def version(p):
        import re
        m = re.search(r"(\d+)\.(\d+)", p)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    if found:
        return max(found, key=version)
    sys.exit("Blender not found: set the BLENDER environment variable to blender(.exe)")


def designs():
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(HERE, "designs", "*.py"))
                  if not os.path.basename(p).startswith("_"))


def load_meta(design):
    p = os.path.join(WORK, design, "meta.json")
    if not os.path.exists(p):
        sys.exit(f"no {p}: run `python pipeline.py render {design}` first")
    return json.load(open(p))


# ------------------------------------------------------------------ stages

def render(design, a):
    work = os.path.join(WORK, design)
    os.makedirs(work, exist_ok=True)
    cmd = [find_blender(), "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.join(HERE, "spritekit", "blender_main.py"), "--", design, work]
    for k in ("only", "facings", "variants", "frames"):
        if getattr(a, k, None):
            cmd += [f"--{k}", getattr(a, k)]
    log_p = os.path.join(work, "blender.log")
    t0 = time.time()
    with open(log_p, "w") as log:
        r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
    text = open(log_p, errors="replace").read()
    n = text.count("\nRENDER ")
    print(f"render {design}: {n} views in {time.time() - t0:.1f}s ({log_p})")
    for line in text.splitlines():
        if line.startswith(("device:", "WARNING")):
            print("  " + line)
    if r.returncode or "Traceback" in text:
        print(text[text.find("Traceback"):][:4000] if "Traceback" in text else text[-4000:])
        sys.exit(f"Blender failed (exit {r.returncode})")


def shade(design):
    from spritekit import shade as sh
    meta = load_meta(design)
    buf = os.path.join(WORK, design, "buffers")
    tex = os.path.join(OUT, design, "tex")
    os.makedirs(tex, exist_ok=True)
    stats, t0, n = {}, time.time(), 0
    for s in meta["sprites"].values():
        for variant, frame in common.jobs(s):
            for facing in s["facings"]:
                st = common.stem(s, facing, variant, frame)
                if not os.path.exists(os.path.join(buf, st + "_id.png")):
                    continue
                stats[st] = sh.shade(os.path.join(buf, st), s, os.path.join(tex, st + ".png"))
                n += 1
    json.dump(stats, open(os.path.join(OUT, design, "stats.json"), "w"), indent=1)
    print(f"shade {design}: {n} textures in {time.time() - t0:.1f}s -> {tex}")


def sheet(design):
    from spritekit import sheet as sh
    for p in sh.build(design, load_meta(design), OUT):
        print("sheet:", p)


def check(design):
    from spritekit import checks
    fails = checks.run(design, load_meta(design), WORK, OUT)
    return fails


def ship(design, dest, dry):
    from spritekit import sheet as sh
    meta = load_meta(design)
    tex = os.path.join(OUT, design, "tex")
    if not dry and not os.path.isdir(dest):
        sys.exit(f"--to {dest} does not exist (point it at the mod's Textures folder)")
    count = 0
    for s in meta["sprites"].values():
        if not s.get("ship", True):
            continue
        if not s.get("ship_dir"):
            print(f"  {s['name']}: no ship_dir, skipped")
            continue
        dst = os.path.join(dest, *s["ship_dir"].split("/"))
        for variant, frame in common.jobs(s):
            for facing in s["facings"]:
                st = common.stem(s, facing, variant, frame)
                for name in (st, common.mask_stem(s, st)):
                    src = os.path.join(tex, name + ".png")
                    if not os.path.exists(src):
                        continue
                    d = os.path.join(dst, "Frames") if frame is not None else dst
                    print(("  would copy " if dry else "  ") + f"{name}.png -> {d}")
                    if not dry:
                        os.makedirs(d, exist_ok=True)
                        shutil.copy2(src, d)
                    count += 1
        if s.get("icon"):
            variant = (s.get("variants") or [None])[0]
            facing = "south" if "south" in s["facings"] else s["facings"][0]
            src = os.path.join(tex, common.stem(s, facing, variant) + ".png")
            print(("  would write " if dry else "  ") + f"icon {s['name']}.png -> {dst}")
            if not dry:
                os.makedirs(dst, exist_ok=True)
                sh.icon(src, common.mask_stem(s, src[:-4]) + ".png", os.path.join(dst, s["name"]))
            count += 2
    print(f"ship {design}: {count} files{' (dry run)' if dry else ''}")


def offsets(design):
    meta = load_meta(design)
    for k in meta["sprites"].values():
        if not k.get("attach"):
            continue
        parent = meta["sprites"][k["attach"]]
        elev = common.view_settings(parent).get("elev", 90.0)
        print(f"{k['name']} on {parent['name']}: pivot {k['pivot']} (hull frame, cells), elev {elev}")
        for f in ("south", "east", "north"):
            x, y = common.oblique_offset(k["pivot"], common.FACING_YAW[f], elev)
            print(f"  {f:5s} ({x:+.3f}, {y:+.3f}) cells from the hull centre (x right, y up)")
        x, y = common.oblique_offset(k["pivot"], common.FACING_YAW["east"], elev)
        print(f"  west  ({-x:+.3f}, {y:+.3f}) (east mirrored)")


def selftest(a):
    a.only = a.facings = a.variants = a.frames = None
    render("calib", a)
    shade("calib")
    sheet("calib")
    return check("calib")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "all", "render", "shade", "sheet", "check", "ship", "offsets", "selftest",
                                       "clean"])
    ap.add_argument("design", nargs="?")
    ap.add_argument("--only")
    ap.add_argument("--facings")
    ap.add_argument("--variants")
    ap.add_argument("--frames")
    ap.add_argument("--to")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "list":
        for d in designs():
            p = os.path.join(WORK, d, "meta.json")
            names = list(json.load(open(p))["sprites"]) if os.path.exists(p) else ["(not rendered yet)"]
            print(f"{d:12s} {', '.join(names)}")
        return
    if a.cmd == "selftest":
        sys.exit(1 if selftest(a) else 0)
    if not a.design:
        ap.error("this command needs a design name (see `python pipeline.py list`)")
    if a.design not in designs():
        sys.exit(f"unknown design {a.design!r}; designs: {', '.join(designs())}")
    if a.cmd == "clean":
        for d in (os.path.join(WORK, a.design), os.path.join(OUT, a.design)):
            shutil.rmtree(d, ignore_errors=True)
        print("cleaned", a.design)
        return
    if a.cmd == "offsets":
        offsets(a.design)
        return
    if a.cmd == "ship":
        if not a.to:
            ap.error("ship needs --to <the mod's Textures folder>")
        ship(a.design, a.to, a.dry_run)
        return
    if a.cmd in ("render", "all"):
        render(a.design, a)
    if a.cmd in ("shade", "all"):
        shade(a.design)
    if a.cmd in ("sheet", "all"):
        sheet(a.design)
    if a.cmd in ("check", "all"):
        sys.exit(1 if check(a.design) else 0)


if __name__ == "__main__":
    main()
