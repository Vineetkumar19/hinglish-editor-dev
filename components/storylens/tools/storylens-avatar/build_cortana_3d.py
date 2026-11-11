"""Build the original StoryLens hologram from the CC0 Innerscene/MakeHuman rig."""
import bpy
from math import cos, pi, sin, copysign, exp, hypot
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
from random import Random
import sys
import bmesh

HERE = Path(__file__).resolve().parent
STATIC = HERE.parents[1] / "hinglish_app" / "static"
OUTPUT = Path(sys.argv[sys.argv.index("--")+1]).resolve() if "--" in sys.argv else HERE / "portrait-match"
OUTPUT.mkdir(parents=True,exist_ok=True)
EXPORT = OUTPUT
sys.path.insert(0,str(HERE))
from cortana_performance import author_actions


def smooth(start, end, x):
    t = min(1, max(0, (x - start) / (end - start)))
    return t*t*(3 - 2*t)


def fit_head(co):
    x,y,z=co
    return Vector((x*(1+.068*smooth(1.345,1.420,z)),y,z-.016*smooth(1.304,1.421,z)))


def eye_fit(co):
    x,y,z=co
    # Give the wider lids enough corneal surface without moving the gaze pivots.
    cornea=smooth(.10993,.124,-y)
    return Vector((x-copysign(.0009,x),y-.0019*cornea,z))


def sculpt_face(co):
    """Fit the front portrait while preserving depth and the original skin weights."""
    x,y,z=co
    side=abs(x)
    forward=smooth(.060,.109,-y)
    jaw=exp(-((z-1.396)/.038)**2)*smooth(.015,.047,side)
    cheek=exp(-((z-1.456)/.027)**2)*smooth(.037,.060,side)
    chin=exp(-((z-1.389)/.016)**2)*(1-smooth(.011,.041,side))
    x*=1-forward*(.052*cheek+.300*jaw)
    new_z=z+.0044*forward*chin

    nose=exp(-((z-1.451)/.017)**2)*(1-smooth(.013,.033,side))
    nose*=smooth(.110,.139,-y)
    x*=1-.26*nose
    y+=.0075*nose
    new_z-=.0034*nose
    lip=exp(-((z-1.4165)/.014)**2)*(1-smooth(.024,.033,side))
    lip*=smooth(.113,.135,-y)
    new_z-=.42*(z-1.4165)*lip+.0041*lip
    new_z+=.0018*lip*smooth(.012,.026,side)
    y+=.0068*lip

    socket=exp(-((side-.0299)/.022)**4-((z-1.4742)/.020)**4)
    socket*=smooth(.091,.111,-y)
    x+=copysign(1,x)*(.05*(side-.0299)-.0009)*socket
    new_z+=socket*(.38*(z-1.4742)+.07*(side-.0299))
    ear=smooth(.067,.082,side)*exp(-((z-1.462)/.031)**2-((y+.061)/.032)**2)
    x-=copysign(.0072*ear,x)
    # Match the tapered chin and the more compact eyelid opening in the portrait.
    chin_taper=exp(-((z-1.397)/.024)**2)*smooth(.017,.055,side)*forward
    x*=1-.077*chin_taper
    mouth=exp(-((z-1.415)/.009)**2)*smooth(.103,.121,-y)*(1-smooth(.027,.041,side))
    x*=1+.105*mouth
    new_z-=.23*(z-1.4742)*socket
    brow=smooth(.102,.116,-y)*exp(-((side-.032)/.023)**4-((z-1.495)/.010)**2)
    y+=.0036*brow
    x-=(1 if x>=0 else -1)*.095*(side-.0295)*socket
    # Match the landmarks in the frontal reference. Keep the side profile
    # three-dimensional and keep the cheek and jaw shape through the turn.
    edge=smooth(.027,.054,side)
    mandibular=exp(-((z-1.401)/.028)**2)*smooth(.041,.091,-y)
    y+=.0038*exp(-((z-1.495)/.013)**2)*exp(-((side-.031)/.027)**4)*smooth(.097,.121,-y)
    x*=1-.115*edge*mandibular
    jaw_corner=exp(-((z-1.394)/.022)**2)*smooth(.013,.039,side)
    new_z+=.0080*jaw_corner*smooth(.042,.090,-y)
    chin_point=exp(-((z-1.384)/.013)**2)*(1-smooth(.013,.037,side))
    new_z-=.0058*chin_point*forward
    nose_tip=exp(-((z-1.437)/.014)**2)*(1-smooth(.012,.026,side))
    nose_tip*=smooth(.112,.141,-y)
    new_z-=.0030*nose_tip
    mouth_position=exp(-((z-1.411)/.011)**2)*(1-smooth(.022,.040,side))
    new_z-=.0028*mouth_position*forward
    lip_corner=exp(-((side-.022)/.009)**2-((z-1.416)/.010)**2)*forward
    new_z-=.0017*lip_corner
    tip=exp(-((side)/.015)**4-((z-1.433)/.011)**2)*smooth(.124,.146,-y)
    y+=.0031*tip
    return Vector((x,y,new_z))


def collar_height(x, depth):
    across=min(abs(x)/.079,1.34)
    arc=across*across
    depth=min(.108,max(-.072,depth))
    edge=smooth(.023,.061,abs(x))*(1-smooth(.068,.102,abs(x)))
    lift=.0065+.012*edge
    return 1.320-.144*depth+.020*arc+.0031*arc*arc+lift


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(HERE / "cortana-human-base.glb"))
rig = bpy.data.objects["base_female_body.rig"]
body = bpy.data.objects["base_female_body"]
eyes = bpy.data.objects["base_female_body.high-poly"]
body.name = "Cortana Body"
eyes.name = "Cortana Eyes"
rig.name = "Cortana Skeleton"


def material(name, color):
    value = bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1)
    value.use_nodes = True
    shader=value.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value=(*color,1)
    shader.inputs["Roughness"].default_value=.71
    return value


skin = material("Cortana Face", (.103, .372, .632))
suit = material("Cortana Suit", (.022, .078, .16))
body.data.materials.clear()
body.data.materials.append(suit)
body.data.materials.append(skin)
# Narrow the cheeks and jaw in the supplied frontal view while keeping the
# weights, eye sockets, lip corners, nose, and skull depth intact.
for vertex in body.data.vertices:
    x,y,z = vertex.co
    front = max(0,min(1,(-y-.048)/.042))
    cheek = max(0,1-abs(z-1.442)/.046)
    side = max(0,min(1,(abs(x)-.032)/.040))
    vertex.co.x *= 1 - .086*front*cheek*side
    vertex.co = sculpt_face(fit_head(vertex.co))

    # Fit the closed, single-piece uniform over the existing skinned topology.
    # Use broad surfaces at the chest and pelvis to carry the fabric's shape.
    bust=smooth(1.061,1.118,z)*(1-smooth(1.211,1.251,z))
    bust*=1-smooth(.079,.145,abs(x))
    bust*=smooth(.071,.122,-y)
    chest_depth=.140+.006*sin((z-1.08)*24)-.018*(x/.148)**2
    vertex.co.y+=(-chest_depth-y)*bust*.94

    pelvis=smooth(.717,.765,z)*(1-smooth(.865,.925,z))
    pelvis*=1-smooth(.054,.122,abs(x))
    front_cloth=.103+.021*smooth(.732,.891,z)-.004*(x/.122)**2
    rear_cloth=.063+.018*smooth(.732,.843,z)-.004*(x/.122)**2
    front_panel=smooth(.022,.080,-y)
    rear_panel=smooth(.021,.061,y)
    vertex.co.y+=pelvis*((-front_cloth-y)*front_panel+(rear_cloth-y)*rear_panel)*.88

# Smooth shallow depth ridges under the upper cloth without changing its silhouette.
groups={}
keys=[]
for vertex in body.data.vertices:
    key=tuple(round(component,6) for component in vertex.co)
    keys.append(key)
    groups.setdefault(key,[]).append(vertex.index)
neighbors={key:set() for key in groups}
for edge in body.data.edges:
    a,b=(keys[index] for index in edge.vertices)
    if a!=b:
        neighbors[a].add(b)
        neighbors[b].add(a)
shoulder={}
for key in groups:
    x,y,z=key
    weight=smooth(.030,.057,abs(x))*(1-smooth(.108,.154,abs(x)))
    weight*=smooth(1.209,1.247,z)*(1-smooth(1.310,1.342,z))*smooth(.044,.083,-y)
    if weight>0 and neighbors[key]:
        shoulder[key]=.62*weight
depths={key:key[1] for key in groups}
for _ in range(9):
    updated={}
    for key,weight in shoulder.items():
        adjacent=neighbors[key]
        average=sum(depths[point] for point in sorted(adjacent))/len(adjacent)
        updated[key]=depths[key]+weight*(average-depths[key])
    depths.update(updated)
for key in shoulder:
    for index in groups[key]:
        body.data.vertices[index].co.y=depths[key]

for vertex in eyes.data.vertices:
    vertex.co=eye_fit(fit_head(vertex.co))
# Retarget the facial pivots in the same rest space as the reshaped face.
bpy.context.view_layer.objects.active=rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bones=rig.data.edit_bones
eye_rig=("eye.","orbicularis03.","orbicularis04.")
def fitted_pivot(bone, point):
    transform=eye_fit if bone.name.startswith(eye_rig) else sculpt_face
    result=transform(fit_head(point))
    if bone.name.startswith(("orbicularis03.","orbicularis04.")):
        result.z-=.23*(result.z-1.4742)
    return result


heads={bone.name:fitted_pivot(bone,bone.head) for bone in bones}
tails={bone.name:fitted_pivot(bone,bone.tail) for bone in bones}
for bone in bones:
    bone.head=heads[bone.name]
    bone.tail=tails[bone.name]
bpy.ops.object.mode_set(mode="OBJECT")
# Boots are modeled as closed physical shells. The hidden foot faces are removed.
work = bmesh.new()
work.from_mesh(body.data)
foot_faces=[face for face in work.faces if face.calc_center_median().z<.134]
bmesh.ops.delete(work,geom=foot_faces,context="FACES")
work.to_mesh(body.data)
work.free()
for face in body.data.polygons:
    x,y,z=face.center
    if z>collar_height(x,-y) and abs(x)<.096:
        face.material_index=1
eyes.data.materials.clear()
eyes.data.materials.append(material("Cortana Eyes", (.075, .226, .392)))


# The front reference has an offset part to the viewer's right. The larger
# lock curves across the forehead toward the viewer's left; the two side
# panels pass outside the eyes and taper toward the jaw.
fringe_profile = (
    (-pi, 2.13), (-1.91, 2.04), (-1.48, 2.075), (-1.12, 2.16),
    (-.94, 2.03), (-.80, 1.89), (-.69, 1.73), (-.59, 1.52),
    (-.47, 1.31), (-.34, 1.17), (-.20, 1.098), (-.05, 1.068),
    (.13, 1.047), (.26, 1.011), (.30, 1.017), (.39, 1.113),
    (.48, 1.27), (.57, 1.49), (.68, 1.70), (.83, 1.98),
    (1.04, 2.13), (1.30, 2.12), (1.62, 2.08), (2.02, 2.06), (pi, 2.13),
)


def fringe_angle(a):
    for i, ((x0,y0),(x1,y1)) in enumerate(zip(fringe_profile,fringe_profile[1:])):
        if a>x1:
            continue
        left=fringe_profile[max(0,i-1)]
        right=fringe_profile[min(len(fringe_profile)-1,i+2)]
        span=x1-x0
        t=(a-x0)/span
        m0=span*(y1-left[1])/(x1-left[0])
        m1=span*(right[1]-y0)/(right[0]-x0)
        return (2*t**3-3*t*t+1)*y0+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*y1+(t**3-t*t)*m1
    return fringe_profile[-1][1]


def hair_surface(a, t, lift=0):
    a = (a + pi) % (2*pi) - pi
    edge = fringe_angle(a)
    angle = .017 + t*(edge-.017)
    radius = sin(angle)
    side = smooth(.51, 1.24, abs(a))
    end = smooth(.70, 1.08, t)
    wave = (.00022 + .00043*t**5)*sin(a*19 + t*2.7)
    fringe_side=smooth(.51,.85,abs(a))*(1-smooth(1.26,1.85,abs(a)))
    tuck = .010*end*side+.023*smooth(.52,1.00,t)*fringe_side
    back_tuck=.016*end*side
    cheek_cover=.007*smooth(.64,1.0,t)*fringe_side
    tip = .00075*end*sin(7*a + .5)
    front = 1 - smooth(.94, 2.3, abs(a))
    comb = front*(.25*(1-t)**2 + .76*sin(pi*min(t, 1))*sin(a-.29))
    width = .0925 + .0035*smooth(.46, .88, t)
    depth = .108 - .008*smooth(.96, 2.6, abs(a))
    depth -= .012*(1-smooth(.38,1.17,abs(a)))*smooth(.40,.83,t)
    # Lower the fuller sweep on the left, tuck the ends into the jaw,
    # and keep a single crown through the side part.
    left_sweep=(1-smooth(-.68,-.04,a))*smooth(.36,.93,t)
    tip_drop=.007*left_sweep+.005*end*fringe_side
    return fit_head(((width+wave-tuck+lift)*radius*sin(a+comb) + .017*(1-t)**2 + tip,
                     -.046-(depth+wave-back_tuck+lift)*radius*cos(a)-cheek_cover,
                     1.489+(.128+.017*(1-min(t,1))**1.4+wave+lift)*cos(angle)-.006*end*side-.007*end*exp(-((abs(a)-1.02)/.34)**2)+tip-tip_drop))


rings,sections=40,144
vertices,faces,uv=[],[],[]
for row in range(rings+1):
    t=row/rings
    for col in range(sections):
        u=col/sections
        a=(u*2-1)*pi
        vertices.append(hair_surface(a,t))
        uv.append((u,t))
for row in range(rings):
    for col in range(sections):
        a=row*sections+col
        b=row*sections+(col+1)%sections
        faces.append((a+sections,b+sections,b,a))
faces.append(tuple(range(sections)))

# Sculpt layered locks with actual tapered tips. The narrow strips follow
# the cap in depth, so profile and rear views have real strands and edges.
rng=Random(631)
for lock in range(76):
    a=-pi+2*pi*(lock+.3*rng.random())/76
    start=.14+rng.uniform(0,.49)
    end=1+rng.uniform(.002,.016)*smooth(.31,.98,abs(a-.22))
    width=rng.uniform(.011,.029) if lock%4 else rng.uniform(.004,.010)
    height=rng.uniform(.00011,.00035)
    offset=len(vertices)
    for step in range(19):
        progress=step/18
        t=start+(end-start)*progress
        taper=max(.055,sin(pi*(.14+.86*progress))**.58)
        drift=.037*sin(a*3.1)*progress**2
        for lane in (-1,0,1):
            u=a+drift+lane*width*taper
            lift=(.00028+height*(1-.68*abs(lane)))*sin(pi*min(.96,progress+.03))**.55
            vertices.append(hair_surface(u,t,lift))
            uv.append(((u+pi)/(2*pi),t))
    for step in range(18):
        for lane in range(2):
            a0=offset+step*3+lane
            faces.append((a0+3,a0+4,a0+1,a0))

mesh=bpy.data.meshes.new("Layered side-part bob geometry")
mesh.from_pydata(vertices,[],faces)
mesh.update()
hair=bpy.data.objects.new("Cortana Bob",mesh)
bpy.context.collection.objects.link(hair)
hair_material=material("Cortana Hair",(.007,.020,.038))
hair.data.materials.append(hair_material)
layer=mesh.uv_layers.new()
for face in mesh.polygons:
    face.use_smooth=True
    crossed=max(uv[v][0] for v in face.vertices)-min(uv[v][0] for v in face.vertices)>.5
    for li in face.loop_indices:
        u,v=uv[mesh.loops[li].vertex_index]
        layer.data[li].uv=(u+1 if crossed and u<.5 else u,v)
hair.parent = rig
head = hair.vertex_groups.new(name="head")
head.add(list(range(len(mesh.vertices))),1,"REPLACE")
modifier = hair.modifiers.new("Head skinning", "ARMATURE")
modifier.object = rig

bootMaterial = material("Cortana Boots", (.018,.065,.108))
boots = []
sections = 48
for side, sign in (("L",1),("R",-1)):
    shell = [
        (.003,-.089,.049,.110),(.018,-.089,.051,.112),(.035,-.073,.048,.101),
        (.057,-.052,.041,.086),(.083,-.031,.038,.066),(.110,-.027,.035,.054),
        (.144,-.024,.034,.049),(.161,-.021,.034,.048),
    ]
    verts=[]
    for z,y,rx,ry in shell:
        for index in range(sections):
            angle=index/sections*2*pi
            cx,cy=cos(angle),sin(angle)
            power=.72 if z<.055 else .97
            verts.append((sign*.165+rx*copysign(abs(cx)**power,cx),
                          y+ry*copysign(abs(cy)**power,cy),z))
    panels=[tuple(range(sections-1,-1,-1))]
    for row in range(len(shell)-1):
        for col in range(sections):
            a=row*sections+col
            b=row*sections+(col+1)%sections
            panels.append((a,b,b+sections,a+sections))
    top=(len(shell)-1)*sections
    panels.append(tuple(range(top,top+sections)))
    mesh=bpy.data.meshes.new("Sculpted ankle boot "+side)
    mesh.from_pydata(verts,[],panels)
    mesh.update()
    boot=bpy.data.objects.new("Cortana Boot "+side,mesh)
    bpy.context.collection.objects.link(boot)
    for face in mesh.polygons:
        face.use_smooth=len(face.vertices)==4
    mesh.uv_layers.new()
    boot.data.materials.append(bootMaterial)
    boot.parent=rig
    group=boot.vertex_groups.new(name="foot."+side)
    group.add(list(range(len(verts))),1,"REPLACE")
    modifier=boot.modifiers.new("Foot skinning","ARMATURE")
    modifier.object=rig
    boots.append(boot)


# Fit real skinned piping to the upper garment. Each sample inherits the
# weights of the triangle under it, so the rails follow torso motion.
body.data.calc_loop_triangles()
triangles=[tuple(t.vertices) for t in body.data.loop_triangles]
points=[v.co.copy() for v in body.data.vertices]
surface_tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
seam_vertices,seam_faces,seam_weights=[],[],[]


def sampled_weights(position,index):
    i,j,k=triangles[index]
    a,b,c=points[i],points[j],points[k]
    e1,e2,p=b-a,c-a,position-a
    d11,d22,d12=e1.dot(e1),e2.dot(e2),e1.dot(e2)
    denominator=d11*d22-d12*d12
    if abs(denominator)<1e-17:
        return {g.group:g.weight for g in body.data.vertices[i].groups}
    v=(p.dot(e1)*d22-p.dot(e2)*d12)/denominator
    w=(p.dot(e2)*d11-p.dot(e1)*d12)/denominator
    weights={}
    for vertex,amount in zip((i,j,k),(1-v-w,v,w)):
        for group in body.data.vertices[vertex].groups:
            weights[group.group]=weights.get(group.group,0)+max(0,amount)*group.weight
    strongest=sorted(weights.items(),key=lambda item:item[1],reverse=True)[:4]
    total=sum(weight for _,weight in strongest) or 1
    return {group:weight/total for group,weight in strongest if weight>.001}


def pipe(hits,radius,closed=False):
    start=len(seam_vertices)
    sections=7
    for i,(point,normal,index) in enumerate(hits):
        previous=hits[(i-1)%len(hits)][0] if closed else hits[max(0,i-1)][0]
        following=hits[(i+1)%len(hits)][0] if closed else hits[min(len(hits)-1,i+1)][0]
        tangent=(following-previous).normalized()
        across=normal.cross(tangent).normalized()
        weights=sampled_weights(point,index)
        taper=1 if closed else .4+.6*smooth(0,7,min(i,len(hits)-1-i))
        center=point+normal*radius*.74
        for col in range(sections):
            a=2*pi*col/sections
            seam_vertices.append(center+radius*taper*(cos(a)*across+sin(a)*normal))
            seam_weights.append(weights)
    for i in range(len(hits) if closed else len(hits)-1):
        for col in range(sections):
            a=start+i*sections+col
            b=start+i*sections+(col+1)%sections
            next_row=start+((i+1)%len(hits))*sections
            seam_faces.append((a,b,next_row+(col+1)%sections,next_row+col))


def interpolate_path(control):
    p=[Vector(pair) for pair in control]
    for i in range(len(p)-1):
        a,b,c,d=p[max(0,i-1)],p[i],p[i+1],p[min(len(p)-1,i+2)]
        for j in range(9):
            t=j/9
            yield (2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t**3)*.5
    yield p[-1]


path=((.055,1.324),(.067,1.298),(.075,1.257),(.076,1.215),(.089,1.184),
      (.110,1.156),(.122,1.119),(.129,1.077),(.125,1.045))
for side in (-1,1):
    for depth in (-1,1):
        for lane,radius in enumerate((.00165,.00126,.00106)):
            hits=[]
            for x,z in interpolate_path(path):
                drift=.0042*lane*smooth(1.327,1.31,z)
                point,normal,index,_=surface_tree.ray_cast(Vector((side*(x+drift),depth*.36,z)),
                    Vector((0,-depth,0)),.36)
                if point is not None:
                    hits.append((point,normal,index))
            if len(hits)>8:
                pipe(hits,radius)

seam_mesh=bpy.data.meshes.new("Fitted collar and shoulder piping")
seam_mesh.from_pydata(seam_vertices,[],seam_faces)
seam_mesh.update()
seams=bpy.data.objects.new("Cortana Garment Piping",seam_mesh)
bpy.context.collection.objects.link(seams)
seam_mesh.materials.append(material("Cortana Piping",(.10,.39,.58)))
for face in seam_mesh.polygons:
    face.use_smooth=True
groups=[seams.vertex_groups.new(name=group.name) for group in body.vertex_groups]
for index,weights in enumerate(seam_weights):
    for group,weight in weights.items():
        groups[group].add([index],weight,"REPLACE")
seams.parent=rig
seam_skin=seams.modifiers.new("Garment skinning","ARMATURE")
seam_skin.object=rig

actions=author_actions(rig)

# Record the neutral, skinned cloth coordinates. The renderer draws the
# parallel chest rails in this basis so the bind-pose shoulder cannot kink them.
bpy.context.view_layer.update()
posed_body=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
assert len(posed_body.data.vertices)==len(body.data.vertices)
tailor=body.data.attributes.new("_TAILOR", "FLOAT_VECTOR", "POINT")
for vertex, attr in zip(posed_body.data.vertices, tailor.data):
    x,y,z=vertex.co
    # Custom glTF attributes keep their component order.
    attr.vector=(x,z+.010,-y)



def collar_profile(front):
    inside=1.343-.024*front+.002*(1-front*front)
    return inside,inside-.0092-.0012*front


def neckline_distances(position):
    x,y,z=position
    depth=-y-.013
    front=depth/max(hypot(x,depth),.001)
    inside,outside=collar_profile(front)
    return inside-z,outside-z


def build_collar():
    # Two closed rings on a single smooth neckline. The garment and the
    # outer ring use the same cut, so the trim meets the band cleanly.
    segments=192
    levels=(0,.11,.23,.40,.57,.72,.86,1)
    vertices,faces,face_materials,weights=[],[],[],[]
    for level in levels:
        for step in range(segments):
            angle=2*pi*step/segments
            x,y=sin(angle),-cos(angle)
            inside,outside=collar_profile(-y)
            height=inside+(outside-inside)*level
            origin=Vector((x*.24,y*.24-.013,height))
            direction=Vector((-x,-y,0))
            hit,normal,index,_=surface_tree.ray_cast(origin,direction,.245)
            assert hit is not None
            relief=.00133+.00028*sin(pi*level)
            vertices.append(hit+normal*relief)
            weights.append(sampled_weights(hit,index))

    for row in range(len(levels)-1):
        for step in range(segments):
            a=row*segments+step
            b=row*segments+(step+1)%segments
            faces.append((a,a+segments,b+segments,b))
            face_materials.append(int(row>=4))
    assert len(faces)==segments*(len(levels)-1)
    mesh=bpy.data.meshes.new("Two round fitted neckline contours")
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    collar=bpy.data.objects.new("Cortana Round Collar",mesh)
    bpy.context.collection.objects.link(collar)
    for label,color in (("Cortana Collar Binding",(.057,.330,.546)),
                        ("Cortana Collar Outer Ring",(.019,.170,.327))):
        fabric=material(label,color)
        shader=fabric.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Emission Color"].default_value=(*color,1)
        shader.inputs["Emission Strength"].default_value=.29
        mesh.materials.append(fabric)
    for face, material_index in zip(mesh.polygons,face_materials):
        face.material_index=material_index
        face.use_smooth=True
    groups=[collar.vertex_groups.new(name=group.name) for group in body.vertex_groups]
    for vertex, influences in enumerate(weights):
        for group, value in influences.items():
            groups[group].add([vertex],value,"REPLACE")
    collar.parent=rig
    collar.modifiers.new("Follow neck and shoulders","ARMATURE").object=rig
    print(f"Blender collar mesh: {len(vertices)} vertices, {len(faces)} faces")
    return collar


round_collar=build_collar()

bpy.ops.object.select_all(action="DESELECT")
for obj in (rig,body,eyes,hair,seams,round_collar,*boots):
    obj.select_set(True)
bpy.context.view_layer.objects.active=rig
if "--native-only" not in sys.argv:
    bpy.ops.export_scene.gltf(filepath=str(EXPORT/"cortana-hologram.glb"),export_format="GLB",
                              use_selection=True,export_attributes=True,export_animations=True,export_animation_mode="ACTIONS",
                              export_frame_step=2,export_materials="EXPORT")

# Align the native Blender skin material with the fitted collar as well.
for face in body.data.polygons:
    center=face.center
    inside,_=neckline_distances(center)
    face.material_index=int(center.z>1.282 and abs(center.x)<.106 and inside<.0035)

# Use the same reference-space registration on the rigged Blender surfaces.
portrait = bpy.data.images.load(str(HERE/"portrait-match"/"cortana-front-reference.png"))
portrait.pack()


def face_projection(x,z):
    px = 611+x*1762
    relative_height = z-1.4742
    py = 265-relative_height*(1830 if relative_height>0 else 1930)
    py -= 12*smooth(1.375,1.410,z)*(1-smooth(1.44,1.4742,z))
    safe_y = min(423,max(165,py))
    left = 511+45*(1-smooth(181,238,safe_y))+66*(1-smooth(149,182,safe_y))+45*smooth(345,423,safe_y)
    right = 730-31*(1-smooth(180,252,safe_y))-43*(1-smooth(146,182,safe_y))-65*smooth(360,430,safe_y)
    return px,py,safe_y,left,right


def registered_portrait(obj, material, region):
    mesh = obj.data
    front = mesh.attributes.new(name="Cortana Portrait Weight", type="FLOAT", domain="POINT")
    projection = mesh.uv_layers.new(name="Cortana Portrait")
    for vertex in mesh.vertices:
        x, y, z = vertex.co
        if region != "eyes":
            px,py,_,left,right = face_projection(x,z)
        if region == "skin":
            orbit = (((abs(x)-.0295)/.0076)**2+((z-1.4742)/.0068)**2)**.5
            weight = smooth(.072,.112,-y)*smooth(1.346,1.405,z)
            weight *= (1-smooth(.052,.079,abs(x)))*smooth(.72,1.20,orbit)*.89
            weight *= smooth(-4,17,min(px-left,right-px))*smooth(146,178,py)*(1-smooth(402,437,py))
        elif region == "hair":
            py+=226*(z-1.4742)*smooth(1.530,1.619,z)
            crown=smooth(1.52,1.60,z)
            outside=max(left-px,px-right)
            weight=smooth(.041-.037*crown,.112-.056*crown,-y)*.89
            weight*=max(1-smooth(115,155,py),smooth(2,28,outside))
        else:
            weight = smooth(.110,.120,-y)*(1-smooth(.007,.0115,abs(abs(x)-.0295)))*.80
        front.data[vertex.index].value = weight
    for loop in mesh.loops:
        x, _, z = mesh.vertices[loop.vertex_index].co
        relative_height = z-1.4742
        if region == "eyes":
            px = (559 if x<0 else 663)+(x-copysign(.0295,x))*1770
            py = 265-relative_height*1790
        else:
            px,py,safe_y,left,right = face_projection(x,z)
            if region == "skin":
                px,py = min(right-7,max(left+7,px)),safe_y
            elif region == "hair":
                py+=226*relative_height*smooth(1.530,1.619,z)
        projection.data[loop.index].uv = (px/1254,1-py/1254)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    surface = nodes.get("Principled BSDF")
    surface.inputs["Roughness"].default_value = {"skin":.64,"hair":.73,"eyes":.52}[region]
    surface.inputs["Specular IOR Level"].default_value = .16 if region=="skin" else .07
    surface.inputs["Emission Strength"].default_value = .38 if region=="skin" else .19
    source = nodes.new("ShaderNodeTexImage")
    source.image = portrait
    source.extension = "CLIP"
    mapping = nodes.new("ShaderNodeUVMap")
    mapping.uv_map = "Cortana Portrait"
    links.new(mapping.outputs["UV"],source.inputs["Vector"])
    weight = nodes.new("ShaderNodeAttribute")
    weight.attribute_name = "Cortana Portrait Weight"
    mix = nodes.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = material.diffuse_color
    mask = weight.outputs["Fac"]
    if region in ("skin","hair"):
        channels = nodes.new("ShaderNodeSeparateColor")
        links.new(source.outputs["Color"],channels.inputs["Color"])
        ramp = nodes.new("ShaderNodeMapRange")
        ramp.interpolation_type = "SMOOTHSTEP"
        low, high = (.040,.133) if region=="skin" else (.052,.148)
        ramp.inputs["From Min"].default_value = low
        ramp.inputs["From Max"].default_value = high
        ramp.inputs["To Min"].default_value = float(region=="hair")
        ramp.inputs["To Max"].default_value = float(region=="skin")
        links.new(channels.outputs["Green" if region=="skin" else "Red"],ramp.inputs["Value"])
        factor = nodes.new("ShaderNodeMath")
        factor.operation = "MULTIPLY"
        links.new(ramp.outputs["Result"],factor.inputs[0])
        links.new(mask,factor.inputs[1])
        mask = factor.outputs[0]
    links.new(mask,mix.inputs[0])
    links.new(source.outputs["Color"],mix.inputs[2])
    links.new(mix.outputs["Color"],surface.inputs["Base Color"])
    links.new(mix.outputs["Color"],surface.inputs["Emission Color"])


registered_portrait(body,skin,"skin")
# The UV direction follows the sculpted locks on every side of the bob.
hair_nodes=hair_material.node_tree.nodes
hair_links=hair_material.node_tree.links
hair_bsdf=hair_nodes.get("Principled BSDF")
hair_bsdf.inputs["Roughness"].default_value=.48
hair_bsdf.inputs["Anisotropic"].default_value=.61
hair_bsdf.inputs["Specular IOR Level"].default_value=.31
hair_uv=hair_nodes.new("ShaderNodeTexCoord")
hair_mapping=hair_nodes.new("ShaderNodeVectorMath")
hair_mapping.operation="MULTIPLY"
hair_mapping.inputs[1].default_value=(190,5,1)
hair_links.new(hair_uv.outputs["UV"],hair_mapping.inputs[0])
hair_fibers=hair_nodes.new("ShaderNodeTexNoise")
hair_fibers.inputs["Scale"].default_value=4
hair_fibers.inputs["Detail"].default_value=2
hair_links.new(hair_mapping.outputs["Vector"],hair_fibers.inputs["Vector"])
hair_shade=hair_nodes.new("ShaderNodeValToRGB")
hair_shade.color_ramp.elements[0].color=(.003,.010,.021,1)
hair_shade.color_ramp.elements[1].color=(.016,.044,.078,1)
hair_links.new(hair_fibers.outputs["Fac"],hair_shade.inputs[0])
hair_links.new(hair_shade.outputs["Color"],hair_bsdf.inputs["Base Color"])
registered_portrait(eyes,eyes.data.materials[0],"eyes")


# Color the fabric in rest space. Interpolating the coordinates keeps the
# narrow reference seams crisp even where the rig's triangles are coarse.
def suit_shader(nodes,links):
    def input_value(socket,value):
        if isinstance(value,(int,float)):
            socket.default_value=value
        else:
            links.new(value,socket)

    def math(operation,a,b=0):
        node=nodes.new("ShaderNodeMath")
        node.operation=operation
        input_value(node.inputs[0],a)
        input_value(node.inputs[1],b)
        return node.outputs[0]

    def add(a,b): return math("ADD",a,b)
    def sub(a,b): return math("SUBTRACT",a,b)
    def mul(a,b): return math("MULTIPLY",a,b)
    def maximum(a,b): return math("MAXIMUM",a,b)
    def absolute(a): return math("ABSOLUTE",a)
    def invert(a): return sub(1,a)
    def product(first,*others):
        for value in others:
            first=mul(first,value)
        return first

    def ease(start,end,value):
        node=nodes.new("ShaderNodeMapRange")
        node.interpolation_type="SMOOTHSTEP"
        node.clamp=True
        input_value(node.inputs["Value"],value)
        input_value(node.inputs["From Min"],start)
        input_value(node.inputs["From Max"],end)
        return node.outputs["Result"]

    def stripe(distance,width,feather=.0018):
        return invert(ease(width,width+feather,absolute(distance)))

    def blend(mask,a,b):
        node=nodes.new("ShaderNodeMixRGB")
        links.new(mask,node.inputs[0])
        for value,socket in zip((a,b),(node.inputs[1],node.inputs[2])):
            if isinstance(value,tuple):
                socket.default_value=(*value,1)
            else:
                links.new(value,socket)
        return node.outputs["Color"]

    rest=nodes.new("ShaderNodeAttribute")
    rest.attribute_name="Cortana Rest Position"
    axes=nodes.new("ShaderNodeSeparateXYZ")
    links.new(rest.outputs["Vector"],axes.inputs["Vector"])
    across=absolute(axes.outputs["X"])
    front=mul(-1,axes.outputs["Y"])
    z=axes.outputs["Z"]

    shoulder_cut=add(.075,sub(mul(.054,invert(ease(1.099,1.223,z))),mul(.022,ease(1.274,1.326,z))))
    shoulder_edge=sub(across,shoulder_cut)
    cuff_height=sub(1.134,mul(.26,maximum(0,sub(across,.200))))
    cuff_delta=sub(z,cuff_height)
    shoulder=product(ease(.002,.010,shoulder_edge),
                     maximum(ease(1.118,1.232,z),ease(-.003,.010,cuff_delta)),
                     invert(ease(.276,.300,across)))
    triangle_delta=sub(across,add(.13,mul(.43,sub(1.282,z))))
    triangle=product(.87,invert(ease(.007,.017,absolute(triangle_delta))),ease(1.219,1.256,z))
    shoulder=mul(shoulder,invert(triangle))

    side_start=add(.117,mul(.016,invert(ease(.60,.93,z))))
    side=product(ease(-.005,.005,sub(across,side_start)),ease(.418,.476,z),
                 invert(ease(1.023,1.138,z)),invert(ease(.195,.232,across)))
    panel=maximum(shoulder,side)

    waist_height=add(.907,mul(.039,ease(.074,.137,across)))
    waist=product(.93,stripe(sub(z,waist_height),.0050,.0007),invert(ease(.165,.185,across)))
    thigh_seam=sub(.083,mul(.024,invert(ease(.630,.704,z))))
    thigh_delta=sub(across,thigh_seam)
    pants=add(stripe(thigh_delta,.00105,.00045),stripe(sub(thigh_delta,.0047),.00105,.00045))
    pants=product(.87,pants,ease(.551,.578,z),invert(ease(.908,.936,z)),ease(.032,.063,front))
    knee_height=add(.417,mul(.048,ease(.029,.065,absolute(sub(across,.137)))))
    knee=product(.88,stripe(sub(z,knee_height),.0041,.0007),ease(.011,.028,front))
    sleeve_edge=product(.86,stripe(cuff_delta,.0031,.0010),ease(.157,.185,across),invert(ease(.276,.300,across)))
    wrist=product(.85,stripe(sub(across,.416),.0025,.001),ease(.81,.91,z))
    hands=product(ease(.416,.430,across),ease(.78,.85,z))
    piping=maximum(maximum(waist,pants),maximum(knee,maximum(sleeve_edge,wrist)))
    fabric=blend(panel,(.008,.034,.061),(.15,.34,.48))
    lined=blend(piping,fabric,(.26,.52,.65))
    return blend(hands,lined,(.17,.335,.426))


rest_position=body.data.attributes.new(name="Cortana Rest Position",type="FLOAT_VECTOR",domain="POINT")
for vertex in body.data.vertices:
    rest_position.data[vertex.index].vector=vertex.co
for boot in boots:
    colors=boot.data.color_attributes.new(name="Reference Footwear",type="FLOAT_COLOR",domain="POINT")
    for vertex in boot.data.vertices:
        x,depth,z=vertex.co
        toe_limit=.034+.025*smooth(.033,.177,-depth)
        toe=(1-smooth(toe_limit-.003,toe_limit+.007,z))*smooth(.008,.017,z)
        dark=(.008,.034,.061)
        grey=(.24,.36,.44)
        sole=.38+.62*smooth(.006,.015,z)
        colors.data[vertex.index].color=(*(sole*(a*(1-toe)+b*toe) for a,b in zip(dark,grey)),1)
nodes=bootMaterial.node_tree.nodes
shoe_tint=nodes.new("ShaderNodeVertexColor")
shoe_tint.layer_name="Reference Footwear"
bootMaterial.node_tree.links.new(shoe_tint.outputs["Color"],nodes.get("Principled BSDF").inputs["Base Color"])
suit.use_nodes=True
nodes=suit.node_tree.nodes
links=suit.node_tree.links
surface=nodes.get("Principled BSDF")
paint=suit_shader(nodes,links)
coords=nodes.new("ShaderNodeTexCoord")
fibers=nodes.new("ShaderNodeTexNoise")
fibers.inputs["Scale"].default_value=282
fibers.inputs["Detail"].default_value=1.1
links.new(coords.outputs["UV"],fibers.inputs["Vector"])
tint=nodes.new("ShaderNodeMapRange")
tint.inputs["To Min"].default_value=.74
tint.inputs["To Max"].default_value=1.20
links.new(fibers.outputs["Fac"],tint.inputs["Value"])
cloth=nodes.new("ShaderNodeMixRGB")
cloth.blend_type="MULTIPLY"
cloth.inputs[0].default_value=.8
links.new(paint,cloth.inputs[1])
links.new(tint.outputs["Result"],cloth.inputs[2])
links.new(cloth.outputs["Color"],surface.inputs["Base Color"])
links.new(cloth.outputs["Color"],surface.inputs["Emission Color"])
bump=nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value=.19
bump.inputs["Distance"].default_value=.00052
links.new(fibers.outputs["Fac"],bump.inputs["Height"])
links.new(bump.outputs["Normal"],surface.inputs["Normal"])
surface.inputs["Emission Strength"].default_value=.18
surface.inputs["Roughness"].default_value=.70


rig.animation_data.action=actions["Listening"]
bpy.context.scene.frame_start=1
bpy.context.scene.frame_end=196
bpy.context.scene.frame_set(1)
bpy.ops.object.select_all(action="DESELECT")
round_collar.select_set(True)
bpy.context.view_layer.objects.active=round_collar
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=="VIEW_3D":
            space=area.spaces.active
            space.region_3d.view_location=Vector((0,0,.85))
            space.region_3d.view_distance=2.45
            space.region_3d.view_perspective="ORTHO"
            space.region_3d.view_rotation=Quaternion((1,0,0),pi/2)
            space.overlay.show_overlays=False
            space.shading.type="MATERIAL"
            space.shading.use_scene_world=True
            space.shading.use_scene_lights=True
# Native portrait inspection cameras and physically lit Blender preview.
scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=640
scene.render.resolution_y=720
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.world=bpy.data.worlds.new("Dark cyan chamber")
scene.world.use_nodes=True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value=(.002,.010,.027,1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value=.46
scene.view_settings.view_transform="AgX"
scene.view_settings.exposure=-.48


def point_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def add_camera(name,position,target):
    data=bpy.data.cameras.new(name)
    data.type="ORTHO"
    data.ortho_scale=.665
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=position
    point_at(obj,target)
    return obj


def area_light(name,position,color,power,size,target=(0,-.01,1.39)):
    data=bpy.data.lights.new(name,"AREA")
    data.color=color
    data.energy=power
    data.shape="DISK"
    data.size=size
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=position
    point_at(obj,target)


front=add_camera("Portrait Front",(.035,-2.2,1.432),(0,-.035,1.325))
three_quarter=add_camera("Portrait Three Quarter",(1.12,-1.94,1.448),(0,-.062,1.454))
face_front=add_camera("Face Front",(0,-2.18,1.454),(0,-.062,1.454))
three_quarter.data.ortho_scale=face_front.data.ortho_scale=.372
profile=add_camera("Portrait Profile",(2.18,-.025,1.44),(0,-.04,1.325))
rear=add_camera("Portrait Rear",(-.09,2.2,1.46),(0,-.025,1.326))
full_front=add_camera("Full front",(.04,-3,1.02),(0,0,.824))
full_front.data.ortho_scale=1.88
full_rear=add_camera("Full rear",(-.09,3,1.05),(0,0,.824))
full_rear.data.ortho_scale=1.88
scene.camera=front
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=="VIEW_3D":
            area.spaces.active.region_3d.view_perspective="CAMERA"
area_light("Soft key",(-.63,-.73,1.98),(.53,.81,1),22,.57)
area_light("Low cool fill",(.65,-.44,1.50),(.23,.55,1),10,.48)
area_light("Projection rim",(.60,.40,1.66),(.027,.51,1),70,.32)
area_light("Shoulder rim",(-.63,.35,1.53),(.036,.62,1),55,.36)

tree=bpy.data.node_groups.new("Cyan projection bloom","CompositorNodeTree")
scene.compositing_node_group=tree
tree.interface.new_socket(name="Image",in_out="OUTPUT",socket_type="NodeSocketColor")
layers=tree.nodes.new("CompositorNodeRLayers")
glow=tree.nodes.new("CompositorNodeGlare")
glow.inputs["Type"].default_value="Fog Glow"
glow.inputs["Quality"].default_value="High"
for name,value in (("Threshold",.19),("Strength",.58),("Size",.25)):
    if name in glow.inputs:
        glow.inputs[name].default_value=value
result=tree.nodes.new("NodeGroupOutput")
tree.links.new(layers.outputs["Image"],glow.inputs["Image"])
tree.links.new(glow.outputs["Image"],result.inputs["Image"])
seams.hide_render=True
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/"StoryLens Cortana 3D.blend"))
if "--render-review" in sys.argv:
    for camera,name,clip,frame in ((full_front,"Blender full front","Listening",1),
        (front,"Blender front","Listening",1),(profile,"Blender profile","Speaking",42),
        (full_front,"Blender gesture","Speaking",40),(full_rear,"Blender step rear","Speaking",77)):
        rig.animation_data.action=actions[clip]
        scene.camera=camera
        scene.frame_set(frame)
        scene.render.filepath=str(OUTPUT/(name+".png"))
        bpy.ops.render.render(write_still=True)


if "--render-face-review" in sys.argv:
    scene.render.resolution_x=720
    scene.render.resolution_y=760
    for camera,name in ((face_front,"Blender Face Front"),(three_quarter,"Blender Face Three Quarter")):
        rig.animation_data.action=actions["Listening"]
        scene.camera=camera
        scene.frame_set(1)
        scene.render.filepath=str(OUTPUT/(name+".png"))
        bpy.ops.render.render(write_still=True)
