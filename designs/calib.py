"""Calibration targets for `python pipeline.py selftest`: one simple shape per view with known pixel sizes.

If a camera, the pixel-aspect trick or the buffer encoding breaks (new Blender version, edited render settings),
these measurements move and the checks fail before any real asset is affected.
"""
import math

from spritekit.kit import Sprite, box

TILT = math.radians(12.0)


def cube(ctx):
    box((0, 0, 0.5), (1, 1, 1), "paint")


def bar(ctx):
    box((0, 0, 0.1), (0.25, 2.0, 0.2), "steel")


def pawn_cube(ctx):
    box((0, 0, 0), (0.5, 0.5, 0.5), "paint")


SPRITES = [
    # oblique 60 deg at 128 px/cell: a 1-cell cube shows a 128 px top and a 128 * cot(60) = 74 px front
    Sprite("CalibCube", cube, "oblique", canvas=(3, 3), facings=["south", "east"], footprint=(1, 1), ship=False,
           expect={"south": {"top": 128, "front": 74}, "east": {"top": 128, "front": 74}}),
    # top-down: a 2-cell bar pointing north is 256 px long
    Sprite("CalibBar", bar, "topdown", canvas=(3, 3), graphic="single", ship=False,
           expect={"north": {"top": 256}}),
    # pawn view at 341.33 px/cell, 12 deg tilt, heights kept true: a 0.5-cell cube shows a 171 px front and
    # a 0.5 * sin(12 deg) * 341.33 = 35 px top
    Sprite("CalibPawn", pawn_cube, "pawn", canvas=(1.5, 1.5), facings=["south"], ship=False,
           expect={"south": {"front": 0.5 * 512 / 1.5, "top": 0.5 * math.sin(TILT) * 512 / 1.5}}),
]
