"""Render a model-check still of Ash: python still_ash.py OUT.png [engine]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402

import ash_model  # noqa: E402
import studio  # noqa: E402

out = sys.argv[1]
engine = sys.argv[2] if len(sys.argv) > 2 else "CYCLES"
studio.reset_scene()
studio.build_studio()
ash_model.build_ash()
studio.add_camera(loc=(0.4, -5.2, 1.25), target=(0, 0, 1.0), lens=50)
studio.render_settings(res=(960, 1080), samples=24, engine=engine)
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
