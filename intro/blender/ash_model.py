"""Procedural low-poly paper-craft model of Ash.

Ash is built from separate parts (torso, head, arms, legs) parented to a root
empty, so the intro animation can pose him with plain object transforms.
Face rule: eyes are plain square bumps and the mouth is a closed flat ridge,
all in the same white paper as the body -- no pupils, no open mouth, ever.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector


def paper_material(name="Paper", color=(0.86, 0.86, 0.84)):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Subsurface Weight"].default_value = 0.08
    bsdf.inputs["Subsurface Radius"].default_value = (0.05, 0.05, 0.05)
    # Fine paper-fibre bump.
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 180.0
    tex.inputs["Detail"].default_value = 8.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _mesh_object(name, bm, mat, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    if parent:
        ob.parent = parent
    return ob


def loft(name, sections, mat, parent=None, jitter=0.012, seed=0, twist=0.0):
    """Faceted tube through (z, rx, ry, n, cx, cy) cross-sections, capped.

    Built in local space; the object origin is the pivot (0, 0, 0).
    """
    rnd = random.Random(seed)
    bm = bmesh.new()
    rings = []
    for i, (z, rx, ry, n, cx, cy) in enumerate(sections):
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n + twist * i + math.pi / n
            j = lambda: rnd.uniform(-jitter, jitter)
            ring.append(bm.verts.new((cx + rx * math.cos(a) + j(),
                                      cy + ry * math.sin(a) + j(),
                                      z + j())))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        n = len(r0)
        for k in range(n):
            # Split each quad into two triangles -> origami-like facets.
            a, b, c, d = r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]
            if (k % 2) == 0:
                bm.faces.new((a, b, c)); bm.faces.new((a, c, d))
            else:
                bm.faces.new((a, b, d)); bm.faces.new((b, c, d))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _mesh_object(name, bm, mat, parent)


def box(name, size, mat, parent=None, loc=(0, 0, 0), bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(loc)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES")
    return _mesh_object(name, bm, mat, parent)


def build_ash(location=(0, 0, 0)):
    """Return dict of Ash's parts. Height ~2.0 units, facing -Y (toward camera)."""
    mat = paper_material()
    root = bpy.data.objects.new("Ash", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = location

    # Body pivots at the hips so hops / leans read naturally.
    body = bpy.data.objects.new("Ash_Body", None)
    bpy.context.scene.collection.objects.link(body)
    body.parent = root
    body.location = (0, 0, 0.86)

    # Torso: broad shoulders tapering to a narrow waist. With n=6 one vertex
    # sits dead-centre front, so a deeper ry gives the origami chest ridge.
    torso = loft("Ash_Torso", [
        (-0.13, 0.21, 0.12, 6, 0, 0),
        (0.08, 0.17, 0.13, 6, 0, -0.01),
        (0.30, 0.25, 0.18, 6, 0, -0.02),
        (0.52, 0.32, 0.17, 6, 0, -0.01),
        (0.62, 0.30, 0.14, 6, 0, 0),
        (0.66, 0.14, 0.10, 6, 0, 0),
    ], mat, parent=body, seed=3, jitter=0.022, twist=0.12)

    neck = loft("Ash_Neck", [
        (0.62, 0.075, 0.07, 5, 0, 0),
        (0.74, 0.07, 0.065, 5, 0, 0),
    ], mat, parent=body, seed=5, jitter=0.004)

    # Head pivots at the neck.
    head = bpy.data.objects.new("Ash_Head", None)
    bpy.context.scene.collection.objects.link(head)
    head.parent = body
    head.location = (0, 0, 0.72)
    box("Ash_Skull", (0.47, 0.42, 0.46), mat, parent=head, loc=(0, 0, 0.24), bevel=0.014)
    # Face: plain raised paper squares for eyes (nothing inside them that could
    # read as a pupil), a small nose wedge and a closed mouth ridge.
    fy = -0.21
    for side, sx in (("L", -0.10), ("R", 0.10)):
        box(f"Ash_Eye_{side}", (0.085, 0.026, 0.075), mat, parent=head, loc=(sx, fy, 0.31), bevel=0.004)
    loft("Ash_Nose", [(0.0, 0.022, 0.012, 3, 0, 0), (0.075, 0.012, 0.034, 3, 0, 0)],
         mat, parent=head, seed=9, jitter=0.0).location = (0, fy - 0.012, 0.19)
    box("Ash_Mouth", (0.14, 0.022, 0.018), mat, parent=head, loc=(0, fy - 0.004, 0.12))

    parts = {"root": root, "body": body, "torso": torso, "neck": neck, "head": head}

    for side, sx in (("L", -1), ("R", 1)):
        # Arms pivot at the shoulders and hang slightly away from the body.
        shoulder = bpy.data.objects.new(f"Ash_Shoulder_{side}", None)
        bpy.context.scene.collection.objects.link(shoulder)
        shoulder.parent = body
        shoulder.location = (sx * 0.33, 0, 0.56)
        shoulder.rotation_euler = (0, sx * math.radians(-12), 0)
        loft(f"Ash_Arm_{side}", [
            (0.04, 0.085, 0.08, 5, 0, 0),
            (-0.26, 0.08, 0.075, 5, 0, 0),
            (-0.50, 0.065, 0.06, 5, 0, 0),
            (-0.60, 0.06, 0.04, 5, 0, 0),
            (-0.70, 0.012, 0.012, 5, 0, 0),
        ], mat, parent=shoulder, seed=11 if sx < 0 else 13, jitter=0.014)
        parts[f"shoulder_{side}"] = shoulder

        # Legs pivot at the hips: wide, trouser-like, slightly flared.
        hip = bpy.data.objects.new(f"Ash_Hip_{side}", None)
        bpy.context.scene.collection.objects.link(hip)
        hip.parent = body
        hip.location = (sx * 0.105, 0, -0.10)
        loft(f"Ash_Leg_{side}", [
            (0.02, 0.12, 0.13, 6, 0, 0),
            (-0.36, 0.115, 0.115, 6, sx * 0.015, 0),
            (-0.66, 0.12, 0.11, 6, sx * 0.03, 0),
            (-0.76, 0.12, 0.15, 6, sx * 0.03, -0.04),
        ], mat, parent=hip, seed=17 if sx < 0 else 19, jitter=0.016, twist=0.2)
        parts[f"hip_{side}"] = hip

    return parts
