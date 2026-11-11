import bpy,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

scene=bpy.context.scene
body=bpy.data.objects['Cortana Body']
cover=bpy.data.objects['Cortana Tailored Lower Suit']
rig=bpy.data.objects['Cortana Skeleton']
used={i for polygon in body.data.polygons for i in polygon.vertices}
sample=[v.index for v in body.data.vertices if v.index in used and .742<v.co.z<.862 and abs(v.co.x)<.128][::3]
assert sample
report={}
for clip,frames in (("Listening",[1,36,49,69,102,151,165]),("Speaking",[1,12,25,40,57,76,92,110,126,140])):
    rig.animation_data.action=bpy.data.actions[clip]
    observations=[]
    for frame in frames:
        scene.frame_set(frame)
        dg=bpy.context.evaluated_depsgraph_get()
        shaped=body.evaluated_get(dg)
        dressed=cover.evaluated_get(dg)
        mesh=dressed.to_mesh()
        tree=BVHTree.FromPolygons([dressed.matrix_world@v.co for v in mesh.vertices],
                                  [tuple(f.vertices) for f in mesh.polygons])
        misses=0
        minimum=1
        for index in sample:
            co=shaped.matrix_world@shaped.data.vertices[index].co
            for direction in (-1,1):
                point,*_=tree.ray_cast(Vector((co.x,direction,co.z)),Vector((0,-direction,0)),2)
                depth=(point.y-co.y)*direction if point is not None else -1
                minimum=min(minimum,depth)
                misses+=depth<0
        observations.append([frame,misses,round(minimum,5)])
        dressed.to_mesh_clear()
    report[clip]=observations
print('sample vertices',len(sample),'[frame, exposed, minimum metres]',json.dumps(report))
assert all(not miss for row in report.values() for _,miss,_ in row),report
