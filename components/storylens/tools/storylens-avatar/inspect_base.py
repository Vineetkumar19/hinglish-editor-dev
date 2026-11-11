import bpy
from mathutils import Vector
from pathlib import Path

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(Path.cwd() / "tools/storylens-avatar/cortana-human-base.glb"))
for o in bpy.context.scene.objects:
    print(o.name,o.type,[round(v,4) for v in o.dimensions], o.matrix_world)
    if o.type=="MESH":
        print(len(o.data.vertices),len(o.data.polygons),len(o.vertex_groups),[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else [])
        for lo,hi in [(1.38,1.43),(1.43,1.47),(1.47,1.51),(1.51,1.55),(1.55,1.62)]:
            pts=[o.matrix_world@v.co for v in o.data.vertices if lo<=(o.matrix_world@v.co).z<hi]
            if pts:
                print("head",lo,hi,[(round(min(p[i] for p in pts),4),round(max(p[i] for p in pts),4)) for i in range(3)])
    if o.type=="ARMATURE":
        for b in o.data.bones:
            if b.name.startswith(("head","eye.","jaw","oris","spine0","neck","upperarm01","lowerarm01","wrist")):
                print(b.name, [round(v,4) for v in o.matrix_world@b.head_local], [round(v,4) for v in o.matrix_world@b.tail_local])
