""""ASH SAYS" intro: build, animate and render the whole 7-second shot.

Usage (with the bpy venv's python):
  python intro.py --out renders/frames/ [--subtitle "TODAY'S TOPIC"]
                  [--res 1920x1080] [--samples 24] [--frames 1-168]
                  [--stills 20,50,90]   # render only these frames as PNGs
                  [--blend out.blend]   # also save the .blend file

Timeline (24 fps, 168 frames = 7 s):
  1-30    crumpled paper ball rolls in and wobbles to a stop
  36-68   the ball stirs, then smoothly uncrumples into a big flat sheet
  62-80   Ash hops out from behind the sheet
  84-98   "ASH SAYS" is stamped onto the sheet; Ash does a proud hop
  100-118 Ash points at the title
  122-146 Ash flips the sheet over to reveal the episode subtitle
  146-168 Ash tilts his head, pleased, and holds
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402  (must precede bmesh)
import bmesh  # noqa: E402

import ash_model  # noqa: E402
import studio  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "ArchivoBlack-Regular.ttf")
FPS = 24
END = 168

SHEET_W, SHEET_H = 2.9, 1.9
SHEET_POS = (-0.75, 0.3, 1.08)
ASH_POS = (1.6, 0.0, 0.0)


def key(ob, path, frame, value, index=-1, interp=None):
    """Set a property and keyframe it; value may be a scalar or a sequence."""
    prop = getattr(ob, path)
    if index >= 0:
        prop[index] = value
    elif hasattr(prop, "__len__"):
        for i, v in enumerate(value):
            prop[i] = v
    else:
        setattr(ob, path, value)
    ob.keyframe_insert(path, index=index, frame=frame)
    if interp:
        for fc in ob.animation_data.action.fcurves:
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    if kp.co[0] == frame:
                        kp.interpolation = interp


def deg(*a):
    return tuple(math.radians(x) for x in a)


# ---------------------------------------------------------------- props

def ink_material():
    mat = bpy.data.materials.new("Ink")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
    bsdf.inputs["Roughness"].default_value = 0.7
    return mat


def crumple_texture(name, scale):
    tex = bpy.data.textures.new(name, "CLOUDS")
    tex.noise_scale = scale
    tex.noise_depth = 1
    tex.noise_type = "SOFT_NOISE"
    return tex


def make_ball(mat):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.42)
    me = bpy.data.meshes.new("Ball")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("PaperBall", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    d = ob.modifiers.new("Crumple", "DISPLACE")
    d.texture = crumple_texture("BallCrumple", 0.22)
    d.strength = 0.22
    d.mid_level = 0.5
    return ob


def crease_offset(x, z, folds):
    """Sum of triangle waves along random directions -> sets of straight
    parallel creases crossing each other, like re-flattened crumpled paper."""
    out = 0.0
    for nx, nz, freq, phase, amp in folds:
        t = (x * nx + z * nz) * freq + phase
        out += amp * (2 * abs(t - math.floor(t + 0.5)) - 0.5)
    return out


def make_sheet(mat, seed=21):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=64, y_segments=42, size=0.5)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for v in bm.verts:  # grid lies in XY; stand it up in XZ facing -Y
        x, y, _ = v.co
        v.co = (x * SHEET_W, 0.0, y * SHEET_H)
    me = bpy.data.meshes.new("Sheet")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new("Sheet", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.location = SHEET_POS

    # Shape key "Crumpled": many random straight folds; value 1 = scrunched, 0 = flat.
    rnd = random.Random(seed)
    folds = []
    for _ in range(14):
        a = rnd.uniform(0, math.pi)
        folds.append((math.cos(a), math.sin(a), rnd.uniform(0.8, 2.6),
                      rnd.uniform(0, 1), rnd.uniform(0.06, 0.16)))
    ob.shape_key_add(name="Basis")
    sk = ob.shape_key_add(name="Crumpled")
    for i, v in enumerate(me.vertices):
        x, _, z = v.co
        # Creases plus a strong cup curl, so the scrunched sheet reads as a wad.
        cup = 0.9 * ((x / SHEET_W) ** 2 + (z / SHEET_H) ** 2) * 4
        sk.data[i].co = (x * 0.75, crease_offset(x, z, folds) + cup, z * 0.75)
    s = ob.modifiers.new("Thickness", "SOLIDIFY")
    s.thickness = 0.008
    return ob


def make_text(name, body, size, mat, parent, back=False, max_w=2.5):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(FONT)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0  # flat ink, like a rubber stamp
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.parent = parent
    # Text faces +Z; turn it to face -Y (front) or +Y (back of the sheet).
    ob.rotation_euler = deg(90, 0, 180) if back else deg(90, 0, 0)
    ob.location = (0, 0.03 if back else -0.03, 0)
    ob.visible_shadow = False  # read as printed ink, not floating letters
    bpy.context.view_layer.update()
    if ob.dimensions.x > max_w:  # auto-fit long subtitles
        cu.size *= max_w / ob.dimensions.x
    return ob


# ---------------------------------------------------------------- animation

def animate_ball(ball, sheet):
    cx, cy, _ = SHEET_POS
    r = 0.42
    ball.location = (-5.2, cy - 0.4, r)
    # Roll in: rotation (rad) = distance / radius about +Y.
    key(ball, "location", 1, (-5.2, cy - 0.4, r))
    key(ball, "rotation_euler", 1, (0, 0, 0))
    key(ball, "location", 30, (cx, cy - 0.4, r))
    key(ball, "rotation_euler", 30, (0, (cx + 5.2) / r, 0))
    # Wobble to a stop.
    for f, a in ((34, -0.18), (37, 0.1), (40, 0.0)):
        key(ball, "rotation_euler", f, (0, (cx + 5.2) / r + a, 0))
    # Anticipation: a small squash and stretch, as if something inside stirs.
    key(ball, "scale", 36, (1, 1, 1))
    key(ball, "scale", 39, (1.07, 1.07, 0.9))
    key(ball, "scale", 42, (0.96, 0.96, 1.06))
    key(ball, "scale", 44, (0, 0, 0))

    # No burst: the crumpled sheet takes the ball's place and smoothly
    # uncrumples, grows and rises into position, then settles with a flutter.
    key(sheet, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(sheet, "scale", 41, (0, 0, 0), interp="CONSTANT")
    key(sheet, "scale", 42, (0.36, 0.36, 0.36))
    key(sheet, "scale", 64, (1, 1, 1))
    key(sheet, "location", 42, (cx, cy - 0.4, r))
    key(sheet, "location", 64, SHEET_POS)
    key(sheet, "rotation_euler", 42, deg(0, 18, 0))
    key(sheet, "rotation_euler", 56, deg(4, -2, 0))
    key(sheet, "rotation_euler", 63, deg(-1.5, 0.5, 0))
    key(sheet, "rotation_euler", 68, deg(0, 0, 0))
    sk = sheet.data.shape_keys.key_blocks["Crumpled"]
    for f, v in ((42, 1.0), (66, 0.035)):
        sk.value = v  # keep a hint of creases in the flattened paper
        sk.keyframe_insert("value", frame=f)
    # Fast start, gentle finish: cubic ease-out from the swap frame.
    for action in (sheet.animation_data.action, sheet.data.shape_keys.animation_data.action):
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                if kp.co[0] == 42:
                    kp.interpolation = "CUBIC"
                    kp.easing = "EASE_OUT"


def animate_title(title, sub, sheet):
    key(title, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(title, "scale", 83, (0, 0, 0), interp="CONSTANT")
    key(title, "scale", 84, (1.25, 1.25, 1.25))
    key(title, "scale", 86, (0.96, 0.96, 0.96))
    key(title, "scale", 88, (1, 1, 1))
    title.rotation_euler = deg(90, -3, 0)  # slightly askew, like a hand stamp
    title.keyframe_insert("rotation_euler", frame=84)
    # The sheet recoils from the stamp.
    key(sheet, "rotation_euler", 84, deg(0, 0, 0))
    key(sheet, "rotation_euler", 86, deg(-6, 0, 0))
    key(sheet, "rotation_euler", 90, deg(2, 0, 0))
    key(sheet, "rotation_euler", 94, deg(0, 0, 0))
    key(sheet, "rotation_euler", 128, deg(0, 0, 0))
    # Flip about the vertical axis to reveal the back.
    key(sheet, "rotation_euler", 140, deg(0, 0, 192))
    key(sheet, "rotation_euler", 146, deg(0, 0, 176))
    key(sheet, "rotation_euler", 152, deg(0, 0, 180))
    key(sub, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(sub, "scale", 127, (0, 0, 0), interp="CONSTANT")
    key(sub, "scale", 128, (1, 1, 1))


def animate_ash(p):
    root, body, head = p["root"], p["body"], p["head"]
    sl, sr = p["shoulder_L"], p["shoulder_R"]
    hl, hr = p["hip_L"], p["hip_R"]
    ax, ay, _ = ASH_POS
    rest_l, rest_r = deg(0, 12, 0), deg(0, -12, 0)

    # Hidden behind the sheet until he hops out.
    hide = (0.35, 1.25, 0.0)
    key(root, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(root, "location", 1, hide, interp="CONSTANT")
    key(root, "scale", 61, (0, 0, 0), interp="CONSTANT")
    key(root, "location", 61, hide, interp="CONSTANT")
    key(root, "scale", 62, (1, 1, 1))
    key(root, "location", 62, hide)
    key(root, "location", 70, (1.0, 0.6, 1.0))
    key(root, "location", 77, (ax, ay, 0))
    key(root, "rotation_euler", 62, deg(0, 0, 40))
    key(root, "rotation_euler", 77, deg(0, 0, 0))
    # Tuck legs and raise arms in the air, then land with a squash.
    for f, leg, arm in ((62, -35, 60), (70, -50, 110), (76, 0, 25), (84, 0, 0)):
        key(hl, "rotation_euler", f, deg(leg, 0, 0))
        key(hr, "rotation_euler", f, deg(leg * 0.6, 0, 0))
        key(sl, "rotation_euler", f, (0, math.radians(12 + arm), 0))
        key(sr, "rotation_euler", f, (0, -math.radians(12 + arm), 0))
    key(root, "scale", 76, (1, 1, 1))
    key(root, "scale", 78, (1.1, 1.1, 0.86))
    key(root, "scale", 82, (0.97, 0.97, 1.04))
    key(root, "scale", 85, (1, 1, 1))

    # Proud little hop right after the stamp.
    key(root, "location", 86, (ax, ay, 0))
    key(root, "location", 91, (ax, ay, 0.32))
    key(root, "location", 96, (ax, ay, 0))
    key(root, "scale", 96, (1, 1, 1))
    key(root, "scale", 97, (1.07, 1.07, 0.9))
    key(root, "scale", 100, (1, 1, 1))
    for f, arm in ((86, 0), (91, 70), (96, 10), (100, 0)):
        key(sl, "rotation_euler", f, (0, math.radians(12 + arm), 0))
        key(sr, "rotation_euler", f, (0, -math.radians(12 + arm), 0))

    # Point at the title: left arm (screen-left, toward the sheet) comes up.
    key(sl, "rotation_euler", 102, rest_l)
    key(sl, "rotation_euler", 108, deg(0, 74, 0))
    key(sl, "rotation_euler", 111, deg(0, 68, 0))
    key(sl, "rotation_euler", 118, deg(0, 70, 0))
    key(sr, "rotation_euler", 102, rest_r)
    key(sr, "rotation_euler", 108, deg(0, -18, 0))
    key(head, "rotation_euler", 100, (0, 0, 0))
    key(head, "rotation_euler", 107, deg(0, 0, -28))
    key(head, "rotation_euler", 116, deg(0, 0, -24))
    key(body, "rotation_euler", 100, (0, 0, 0))
    key(body, "rotation_euler", 108, deg(0, -6, 0))

    # Reach for the sheet's edge and swipe it over.
    key(root, "location", 118, (ax, ay, 0))
    key(root, "location", 126, (ax - 0.35, ay, 0))
    key(sl, "rotation_euler", 124, deg(0, 92, 0))
    key(sl, "rotation_euler", 128, deg(0, 96, 0))
    key(sl, "rotation_euler", 134, deg(-35, 70, 0))
    key(sl, "rotation_euler", 142, rest_l)
    key(body, "rotation_euler", 124, deg(0, -10, 0))
    key(body, "rotation_euler", 130, deg(0, -4, -14))
    key(body, "rotation_euler", 140, (0, 0, 0))
    key(head, "rotation_euler", 128, deg(0, 0, -20))
    key(head, "rotation_euler", 140, deg(0, 0, -10))
    key(root, "location", 140, (ax - 0.35, ay, 0))
    key(root, "location", 148, (ax - 0.2, ay, 0))

    # Pleased head tilt and settle.
    key(head, "rotation_euler", 148, deg(0, 0, -10))
    key(head, "rotation_euler", 154, deg(0, 16, -12))
    key(head, "rotation_euler", 168, deg(0, 14, -12))
    key(sr, "rotation_euler", 146, rest_r)
    key(sr, "rotation_euler", 152, deg(0, -30, 0))  # little hand flourish
    key(sr, "rotation_euler", 160, deg(0, -16, 0))
    key(root, "scale", 150, (1, 1, 1))
    key(root, "scale", 158, (1.0, 1.0, 1.02))
    key(root, "scale", 166, (1, 1, 1))


# ---------------------------------------------------------------- main

def build(subtitle):
    studio.reset_scene()
    studio.build_studio()
    paper = ash_model.paper_material()
    ink = ink_material()
    ball = make_ball(paper)
    sheet = make_sheet(ash_model.paper_material("SheetPaper", (0.9, 0.89, 0.86)))
    title = make_text("Title", "ASH SAYS", 0.62, ink, sheet)
    sub = make_text("Subtitle", subtitle, 0.46, ink, sheet, back=True)
    parts = ash_model.build_ash(ASH_POS)

    animate_ball(ball, sheet)
    animate_title(title, sub, sheet)
    animate_ash(parts)

    studio.add_camera(loc=(0.35, -7.6, 1.3), target=(0.25, 0, 1.12), lens=40)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, END
    return scene


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--subtitle", default="TODAY'S TOPIC")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--frames", default=f"1-{END}")
    ap.add_argument("--stills", default="")
    ap.add_argument("--blend", default="")
    ap.add_argument("--motion-blur", action="store_true")
    a = ap.parse_args(argv)

    scene = build(a.subtitle)
    w, h = (int(x) for x in a.res.split("x"))
    studio.render_settings(res=(w, h), samples=a.samples, fps=FPS)
    scene.render.use_motion_blur = a.motion_blur
    scene.render.use_persistent_data = True
    if a.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    os.makedirs(a.out, exist_ok=True)
    if a.stills:
        for f in (int(x) for x in a.stills.split(",")):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(a.out, f"still_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
        return
    s, e = (int(x) for x in a.frames.split("-"))
    scene.frame_start, scene.frame_end = s, e
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(a.out, "f_")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
