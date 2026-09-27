""""ASH PROJECT" intro: build, animate and render the whole 8-second shot.

Usage (with the bpy venv's python):
  python intro.py --out renders/frames/ [--subtitle "TODAY'S TOPIC"]
                  [--res 1920x1080] [--samples 24] [--frames 1-192]
                  [--stills 20,50,90]   # render only these frames as PNGs
                  [--blend out.blend]   # also save the .blend file

Timeline (24 fps, 192 frames = 8 s):
  1-28    a big crumpled paper ball rolls in and wobbles to a stop
  32-58   it uncrumples and flies at the camera until the sheet fills the
          screen; "ASH PROJECT" is printed on it, so the words unfold too
  58-90   full-screen hold so the title can be read; at frame 60 a hidden
          cut puts the sheet in Ash's outstretched hands at the lens
  90-132  Ash pulls the sheet down to his chest while the camera dollies
          back, revealing him holding it
  134-170 the episode subtitle pops up letter by letter beside him;
          Ash looks over at it and tilts his head
  170-192 hold
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402  (must precede bmesh)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import ash_model  # noqa: E402
import studio  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "ArchivoBlack-Regular.ttf")
FPS = 24
END = 192

CAM_LOC, CAM_TARGET, LENS = (0.0, -7.6, 1.25), (0.0, 0.0, 1.0), 40
SHEET_W, SHEET_H = 2.9, 1.9
ASH_POS = (-1.3, 0.0, 0.0)
HELD_SCALE = 0.45                       # sheet size in Ash's hands
HELD_POS = (ASH_POS[0], -0.34, 1.12)    # just under his chin, in front of his chest
EXT_POS = (ASH_POS[0], -0.62, 1.45)     # at arm's length, pushed toward the lens
BALL_R = 0.7
BALL_POS = (0.0, -3.0, BALL_R)
# Where the flattened sheet overfills the whole frame, on the camera's axis.
_d = 2.9
COVER_POS = (0.0, CAM_LOC[1] + _d, CAM_LOC[2] - _d * (CAM_LOC[2] - CAM_TARGET[2]) / (CAM_TARGET[1] - CAM_LOC[1]))
# The hidden cut: once the sheet fills the frame, camera and sheet jump so the
# sheet is in Ash's outstretched hands. Scaling the camera-to-sheet offset by
# HELD_SCALE keeps the image identical, so the jump can't be seen.
CUT = 60
CAM_CLOSE = tuple(e + HELD_SCALE * (c - v) for e, c, v in zip(EXT_POS, CAM_LOC, COVER_POS))
TARGET_CLOSE = tuple(c + (t - l) for c, t, l in zip(CAM_CLOSE, CAM_TARGET, CAM_LOC))
FILL_LOC, FILL_ENERGY = (CAM_LOC[0] + 1.2, CAM_LOC[1] - 0.5, CAM_LOC[2] + 1.6), 260
# The studio key/rim reach the close position too, so trim the fill there.
CLOSE_FILL_TRIM = 0.27
FILL_CLOSE = tuple(e + HELD_SCALE * (f - v) for e, f, v in zip(EXT_POS, FILL_LOC, COVER_POS))
TOPIC_CENTER = (1.55, 0.0, 1.15)
TOPIC_MAX_W = 3.1


def key(ob, path, frame, value, index=-1, interp=None, easing=None):
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
    if interp or easing:
        for fc in ob.animation_data.action.fcurves:
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    if kp.co[0] == frame:
                        if interp:
                            kp.interpolation = interp
                        if easing:
                            kp.easing = easing


def deg(*a):
    return tuple(math.radians(x) for x in a)


# ---------------------------------------------------------------- props

def crumple_texture(name, scale):
    tex = bpy.data.textures.new(name, "CLOUDS")
    tex.noise_scale = scale
    tex.noise_depth = 1
    tex.noise_type = "SOFT_NOISE"
    return tex


def make_ball(mat):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=BALL_R)
    me = bpy.data.meshes.new("Ball")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("PaperBall", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    d = ob.modifiers.new("Crumple", "DISPLACE")
    d.texture = crumple_texture("BallCrumple", 0.35)
    d.strength = 0.36
    d.mid_level = 0.5
    return ob


def title_image(text, path, w=2048):
    """Render the printed title as a transparent PNG for the sheet's UVs."""
    from PIL import Image, ImageDraw, ImageFont
    h = int(w * SHEET_H / SHEET_W)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    size = 400
    while True:
        font = ImageFont.truetype(FONT, size)
        l, t, r, b = dr.textbbox((0, 0), text, font=font)
        if r - l <= w * 0.82:
            break
        size -= 8
    dr.text(((w - (r - l)) / 2 - l, (h - (b - t)) / 2 - t), text, font=font, fill=(10, 10, 12, 255))
    img.save(path)
    return path


def printed_paper_material(image_path):
    mat = bpy.data.materials.new("PrintedPaper")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Subsurface Weight"].default_value = 0.05
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(image_path)
    img.interpolation = "Cubic"
    img.extension = "CLIP"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.9, 0.89, 0.86, 1)
    nt.links.new(img.outputs["Alpha"], mix.inputs["Factor"])
    nt.links.new(img.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 180.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.05
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


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
    bm.loops.layers.uv.new("UVMap")  # create_grid only fills an existing UV layer
    bmesh.ops.create_grid(bm, x_segments=128, y_segments=84, size=0.5, calc_uvs=True)
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

    # Shape key "Crumpled": crossing crease sets plus a cup curl; 1 = wad, 0 = flat.
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
        cup = 0.9 * ((x / SHEET_W) ** 2 + (z / SHEET_H) ** 2) * 4
        sk.data[i].co = (x * 0.75, crease_offset(x, z, folds) + cup, z * 0.75)
    s = ob.modifiers.new("Thickness", "SOLIDIFY")
    s.thickness = 0.008
    return ob


def make_topic_letters(text, mat):
    """One paper-craft 3D object per character, laid out and auto-fitted."""
    from PIL import ImageFont
    metrics = ImageFont.truetype(FONT, 1000)
    size = 0.62
    letters, widths = [], []
    for i, ch in enumerate(text):
        # Advance widths from the font itself (text dimensions are unreliable
        # before the depsgraph evaluates the curve).
        widths.append(metrics.getlength(ch) / 1000 * size)
        if ch == " ":
            letters.append(None)
            continue
        cu = bpy.data.curves.new(f"Topic{i}", "FONT")
        cu.body = ch
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
        cu.size = size
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.extrude = 0.05
        cu.bevel_depth = 0.006
        ob = bpy.data.objects.new(f"Topic{i}", cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(mat)
        ob.rotation_euler = deg(90, 0, 0)
        letters.append(ob)
    gap = size * 0.02
    total = sum(widths) + gap * (len(widths) - 1)
    fit = min(1.0, TOPIC_MAX_W / total)
    x = TOPIC_CENTER[0] - total * fit / 2
    out = []
    for ob, w in zip(letters, widths):
        if ob:
            ob.location = (x + w * fit / 2, TOPIC_CENTER[1], TOPIC_CENTER[2])
            ob["fit"] = fit
            out.append(ob)
        x += (w + gap) * fit
    return out


# ---------------------------------------------------------------- animation

def animate_ball(ball):
    bx, by, r = BALL_POS
    x0 = -5.8
    key(ball, "location", 1, (x0, by, r))
    key(ball, "rotation_euler", 1, (0, 0, 0))
    key(ball, "location", 26, (bx, by, r))
    key(ball, "rotation_euler", 26, (0, (bx - x0) / r, 0))
    for f, a in ((29, -0.14), (32, 0.07), (34, 0.0)):
        key(ball, "rotation_euler", f, (0, (bx - x0) / r + a, 0))
    # Anticipation: squash and stretch, as if something inside stirs.
    key(ball, "scale", 30, (1, 1, 1))
    key(ball, "scale", 33, (1.07, 1.07, 0.9))
    key(ball, "scale", 36, (0.96, 0.96, 1.06))
    key(ball, "scale", 38, (0, 0, 0))


def animate_sheet(sheet):
    # Takes the ball's place as a wad, uncrumples and flies at the camera.
    key(sheet, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(sheet, "scale", 35, (0, 0, 0), interp="CONSTANT")
    key(sheet, "scale", 36, (0.5, 0.5, 0.5), interp="CUBIC", easing="EASE_OUT")
    key(sheet, "scale", 58, (1, 1, 1))
    key(sheet, "location", 36, BALL_POS, interp="CUBIC", easing="EASE_OUT")
    key(sheet, "location", 58, COVER_POS)
    key(sheet, "rotation_euler", 36, deg(0, 20, 0), interp="CUBIC", easing="EASE_OUT")
    key(sheet, "rotation_euler", 56, deg(3, -1.5, 0))
    key(sheet, "rotation_euler", 61, deg(-1, 0.5, 0))
    key(sheet, "rotation_euler", 66, deg(0, 0, 0))
    sk = sheet.data.shape_keys.key_blocks["Crumpled"]
    sk.value = 1.0
    sk.keyframe_insert("value", frame=36)
    sk.value = 0.03  # a hint of creases stays in the flattened paper
    sk.keyframe_insert("value", frame=60)
    for fc in sheet.data.shape_keys.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            if kp.co[0] == 36:
                kp.interpolation, kp.easing = "CUBIC", "EASE_OUT"

    # The hidden cut: from here on the sheet is in Ash's outstretched hands.
    key(sheet, "location", CUT - 1, COVER_POS, interp="CONSTANT")
    key(sheet, "scale", CUT - 1, (1, 1, 1), interp="CONSTANT")
    key(sheet, "location", CUT, EXT_POS)
    key(sheet, "scale", CUT, (HELD_SCALE,) * 3)
    # Hold for reading, then Ash pulls it down to his chest.
    key(sheet, "location", 90, EXT_POS, interp="CUBIC", easing="EASE_IN_OUT")
    key(sheet, "rotation_euler", 90, (0, 0, 0))
    key(sheet, "rotation_euler", 104, deg(-10, 0, 0))
    key(sheet, "location", 116, HELD_POS)
    key(sheet, "rotation_euler", 116, deg(-4, 0, 0))
    # Settle bounce, then ride along with Ash's idle motion.
    hx, hy, hz = HELD_POS
    key(sheet, "location", 120, (hx, hy, hz - 0.04))
    key(sheet, "location", 125, (hx, hy, hz + 0.01))
    key(sheet, "rotation_euler", 122, deg(2, 0, 0))
    key(sheet, "location", 130, HELD_POS)
    key(sheet, "rotation_euler", 130, deg(0, 0, 0))
    key(sheet, "location", 150, HELD_POS)
    key(sheet, "location", 162, (hx + 0.03, hy, hz))
    key(sheet, "rotation_euler", 162, deg(0, -3, 0))
    key(sheet, "location", 192, (hx + 0.03, hy, hz))


def animate_camera(cam, target, fill):
    """Jump in with the hidden cut, then dolly back out as Ash lowers the sheet."""
    for ob, far, near in ((cam, CAM_LOC, CAM_CLOSE), (target, CAM_TARGET, TARGET_CLOSE),
                          (fill, FILL_LOC, FILL_CLOSE)):
        key(ob, "location", 1, far, interp="CONSTANT")
        key(ob, "location", CUT - 1, far, interp="CONSTANT")
        key(ob, "location", CUT, near)
        key(ob, "location", 92, near, interp="CUBIC", easing="EASE_IN_OUT")
        key(ob, "location", 132, far)
    # Keep the sheet equally bright across the cut (area light ~ 1/distance^2).
    fd = fill.data
    for f, e in ((1, FILL_ENERGY), (CUT - 1, FILL_ENERGY), (CUT, FILL_ENERGY * HELD_SCALE ** 2 * CLOSE_FILL_TRIM),
                 (92, FILL_ENERGY * HELD_SCALE ** 2 * CLOSE_FILL_TRIM), (132, FILL_ENERGY)):
        fd.energy = e
        fd.keyframe_insert("energy", frame=f)
    for fc in fd.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            if kp.co[0] == CUT - 1:
                kp.interpolation = "CONSTANT"


def arm_euler(shoulder, target_world):
    """Euler (in the shoulder's parent space) that points the arm at target."""
    bpy.context.view_layer.update()
    origin = shoulder.matrix_world.translation
    d = (Vector(target_world) - origin).normalized()
    return Vector((0, 0, -1)).rotation_difference(d).to_euler()


def animate_ash(p):
    root, body, head = p["root"], p["body"], p["head"]
    sl, sr = p["shoulder_L"], p["shoulder_R"]
    # Hands grip the sheet's side edges, at arm's length and at the chest.
    # Computed before any scale keys, which would collapse the rig's matrices.
    half = SHEET_W * HELD_SCALE / 2

    def grips(pos):
        x, y, z = pos
        return (arm_euler(sl, (x - half + 0.02, y + 0.02, z - 0.02)),
                arm_euler(sr, (x + half - 0.02, y + 0.02, z - 0.02)))
    ext_l, ext_r = grips(EXT_POS)
    held_l, held_r = grips(HELD_POS)

    # Invisible until the hidden cut, then already holding the sheet up.
    key(root, "scale", 1, (0, 0, 0), interp="CONSTANT")
    key(root, "scale", CUT - 1, (0, 0, 0), interp="CONSTANT")
    key(root, "scale", CUT, (1, 1, 1))
    for f, l, r in ((CUT, ext_l, ext_r), (90, ext_l, ext_r), (116, held_l, held_r)):
        key(sl, "rotation_euler", f, l)
        key(sr, "rotation_euler", f, r)
    for fc in sl.animation_data.action.fcurves[:] + sr.animation_data.action.fcurves[:]:
        for kp in fc.keyframe_points:
            if kp.co[0] == 90:
                kp.interpolation, kp.easing = "CUBIC", "EASE_IN_OUT"

    # Leans back a touch while pulling, then a small settle.
    key(body, "rotation_euler", 90, (0, 0, 0))
    key(body, "rotation_euler", 108, deg(-5, 0, 0))
    key(body, "rotation_euler", 118, deg(4, 0, 0))
    key(body, "rotation_euler", 128, (0, 0, 0))
    key(root, "scale", 116, (1, 1, 1))
    key(root, "scale", 120, (1.04, 1.04, 0.95))
    key(root, "scale", 126, (0.99, 0.99, 1.02))
    key(root, "scale", 130, (1, 1, 1))

    # Looks over at the subtitle as it appears, then a pleased tilt.
    key(head, "rotation_euler", 134, (0, 0, 0))
    key(head, "rotation_euler", 142, deg(0, 0, 30))
    key(head, "rotation_euler", 150, deg(0, 0, 26))
    key(head, "rotation_euler", 160, deg(0, 0, 14))
    key(head, "rotation_euler", 168, deg(0, -15, 12))
    key(head, "rotation_euler", 192, deg(0, -13, 12))
    key(body, "rotation_euler", 150, (0, 0, 0))
    key(body, "rotation_euler", 162, deg(0, 0, 8))
    key(body, "rotation_euler", 192, deg(0, 0, 8))


def animate_topic(letters, start=136, stagger=2):
    for i, ob in enumerate(letters):
        f0 = start + i * stagger
        fit = ob["fit"]
        loc = tuple(ob.location)
        key(ob, "scale", 1, (0, 0, 0), interp="CONSTANT")
        key(ob, "scale", f0, (0, 0, 0))
        key(ob, "location", f0, (loc[0], loc[1], loc[2] - 0.25))
        key(ob, "rotation_euler", f0, deg(90, 0, -25))
        key(ob, "scale", f0 + 4, (fit * 1.18,) * 3)
        key(ob, "location", f0 + 4, (loc[0], loc[1], loc[2] + 0.06))
        key(ob, "scale", f0 + 7, (fit * 0.96,) * 3)
        key(ob, "location", f0 + 7, loc)
        key(ob, "rotation_euler", f0 + 7, deg(90, 0, 3))
        key(ob, "scale", f0 + 10, (fit,) * 3)
        key(ob, "rotation_euler", f0 + 10, deg(90, 0, 0))


# ---------------------------------------------------------------- main

def build(subtitle, title="ASH PROJECT", workdir="/tmp"):
    studio.reset_scene()
    studio.build_studio()
    paper = ash_model.paper_material()
    ball = make_ball(paper)
    img = title_image(title, os.path.join(workdir, "ash_title_print.png"))
    sheet = make_sheet(printed_paper_material(img))
    parts = ash_model.build_ash(ASH_POS)
    letters = make_topic_letters(subtitle.upper(), ash_model.paper_material("TopicInk", (0.035, 0.035, 0.04)))

    # Soft frontal light from just above the camera, so the sheet is lit
    # when it fills the frame (the studio key sits off to the side).
    fl = bpy.data.lights.new("CoverFill", "AREA")
    fl.size, fl.energy = 4.0, FILL_ENERGY
    fill = bpy.data.objects.new("CoverFill", fl)
    fill.location = FILL_LOC
    fill.rotation_euler = deg(80, 0, 10)
    bpy.context.scene.collection.objects.link(fill)
    cam = studio.add_camera(loc=CAM_LOC, target=CAM_TARGET, lens=LENS)

    animate_ball(ball)
    animate_sheet(sheet)
    animate_ash(parts)
    animate_topic(letters)
    animate_camera(cam, bpy.data.objects["CamTarget"], fill)

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, END
    return scene


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--subtitle", default="TODAY'S TOPIC")
    ap.add_argument("--title", default="ASH PROJECT")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--frames", default=f"1-{END}")
    ap.add_argument("--stills", default="")
    ap.add_argument("--blend", default="")
    ap.add_argument("--motion-blur", action="store_true")
    a = ap.parse_args(argv)

    os.makedirs(a.out, exist_ok=True)
    scene = build(a.subtitle, a.title, os.path.abspath(a.out))
    w, h = (int(x) for x in a.res.split("x"))
    studio.render_settings(res=(w, h), samples=a.samples, fps=FPS)
    scene.render.use_motion_blur = a.motion_blur
    scene.render.use_persistent_data = True
    if a.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
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
