# Agent notes

This repository turns Python geometry code into finished 2D game sprites (Blender renders data passes, numpy
shades them). **Read README.md before changing anything**; section 1 has the rules, sections 7-9 the API.

Short version:

- `python pipeline.py selftest` first; it must report 0 failures.
- New art = a new file in `designs/`, copied from the closest demo (`rover.py` vehicle, `relay.py` building and
  animation, `trooper.py` apparel). Leave `spritekit/` alone unless you are adding a general feature, and re-run
  every demo if you do.
- `python pipeline.py all <design>`, then look at `out/<design>/zoom.png` and `sheet.png` with your image tool
  after every change. Iterate on one facing and variant (`--facings south --variants Male --frames none`).
- Look changes are re-shades (`python pipeline.py shade <design>`), no Blender needed.
- `python pipeline.py check <design>` must pass before the design is done.
- No AI image generation, no game textures shipped.
