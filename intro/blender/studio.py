"""Grey seamless studio: cyclorama backdrop, soft lights, camera, render settings."""
import math

import bmesh
import bpy


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def build_studio(bg=(0.22, 0.225, 0.235)):
    scene = bpy.context.scene
    mat = bpy.data.materials.new("Backdrop")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*bg, 1)
    bsdf.inputs["Roughness"].default_value = 0.95

    # Floor that curves up into a back wall (seamless sweep).
    bm = bmesh.new()
    pts = [(y, 0.0) for y in (-12.0, -6.0, 0.0, 2.0)]
    r = 3.0
    for i in range(1, 17):
        a = i / 16 * math.pi / 2
        pts.append((2.0 + r * math.sin(a), r - r * math.cos(a)))
    pts.append((2.0 + r, 14.0))
    rows = []
    for x in (-20.0, 20.0):
        rows.append([bm.verts.new((x, y, z)) for y, z in pts])
    for k in range(len(pts) - 1):
        bm.faces.new((rows[0][k], rows[1][k], rows[1][k + 1], rows[0][k + 1]))
    me = bpy.data.meshes.new("Backdrop")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Backdrop", me)
    ob.data.materials.append(mat)
    scene.collection.objects.link(ob)

    def area(name, loc, rot, size, energy, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
        ld.energy = energy
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = [math.radians(a) for a in rot]
        scene.collection.objects.link(lo)
        return lo

    area("Key", (-5.5, -3.5, 4.5), (55, 0, -58), (3.0, 3.0), 700)
    area("Fill", (5.0, -5.0, 2.0), (75, 0, 42), (5.0, 3.0), 90, (0.95, 0.97, 1.0))
    area("Rim", (2.5, 3.0, 4.0), (-50, 0, 150), (2.0, 1.0), 260)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*bg, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    scene.world = world


def add_camera(loc=(0, -9.0, 1.6), target=(0, 0, 1.2), lens=50):
    scene = bpy.context.scene
    cd = bpy.data.cameras.new("Camera")
    cd.lens = lens
    cam = bpy.data.objects.new("Camera", cd)
    scene.collection.objects.link(cam)
    cam.location = loc
    tgt = bpy.data.objects.new("CamTarget", None)
    scene.collection.objects.link(tgt)
    tgt.location = target
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    scene.camera = cam
    return cam


def render_settings(res=(1920, 1080), samples=64, engine="CYCLES", fps=24):
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 2
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
        scene.cycles.adaptive_threshold = 0.02
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
