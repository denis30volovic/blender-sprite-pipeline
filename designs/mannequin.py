"""Stand-in pawn: the bare body (five body types) and head, rendered in flesh. Not shipped.

Review sheets draw apparel over these, and the skin check uses the head to ignore what the head layer covers.
The dark eye marks show where the game draws eyes, so visors and slits can be lined up with them.
"""
from spritekit.kit import BODY_TYPES, Body, Head, Sprite, ellipsoid, eye_z


def body(ctx):
    Body(ctx.variant).mesh("flesh")


def head(ctx):
    h = Head()
    h.mesh("flesh")
    for s in (-1, 1):
        p = h.point(s * 20, -14, 0.0)
        ellipsoid((p.x, p.y, eye_z(p.y)), (0.03, 0.02, 0.03), "dark", segments=8, rings=6)


SPRITES = [
    Sprite("Mannequin", body, "pawn", canvas=(1.5, 1.5), variants=BODY_TYPES, layer="body", ship=False),
    Sprite("MannequinHead", head, "pawn", canvas=(1.5, 1.5), layer="head", ship=False),
]
