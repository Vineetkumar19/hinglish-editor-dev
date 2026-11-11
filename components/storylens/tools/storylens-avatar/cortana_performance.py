"""Keyframed Cortana performances for the Blender scene and StoryLens GLB."""
from math import acos, atan2, radians, sqrt
from mathutils import Quaternion, Vector
import bpy

UP=Vector((0,0,1))
FORWARD=Vector((0,-1,0))
SIDE=Vector((1,0,0))


def author_actions(rig):
    bones=rig.pose.bones
    scene=bpy.context.scene
    scene.render.fps=24
    bpy.context.view_layer.update()
    anchors={side:bones["foot."+side].head.copy() for side in ("L","R")}
    # Full-body source at 18–22 s has a narrow stance and arms at the sides.
    for ankle in anchors.values():
        ankle.x*=.54
    soles={side:bones["foot."+side].matrix.to_quaternion() for side in ("L","R")}
    keyed={"root","spine03","spine01","neck01","head"}
    for side in ("L","R"):
        keyed.update(name+"."+side for name in (
            "upperarm01","lowerarm01","wrist","upperleg01","lowerleg01","foot",
            "levator05","finger1-1","finger2-1","finger2-2","finger3-1","finger3-2",
            "finger4-1","finger4-2","finger5-1","finger5-2"))

    def update():
        bpy.context.view_layer.update()

    def world_rotation(bone,rotation):
        matrix=rotation.to_matrix().to_4x4()
        matrix.translation=bone.head
        bone.matrix=matrix
        update()

    def rotate(bone,axis,angle):
        world_rotation(bone,Quaternion(axis,angle) @ bone.matrix.to_quaternion())

    def point(bone,tip,direction):
        current=(tip.head-bone.head).normalized()
        turn=current.rotation_difference(Vector(direction).normalized())
        world_rotation(bone,turn @ bone.matrix.to_quaternion())

    def shift(bone,xyz):
        matrix=bone.matrix.copy()
        matrix.translation+=Vector(xyz)
        bone.matrix=matrix
        update()

    def foot(side,offset):
        hip=bones["upperleg01."+side]
        shin=bones["lowerleg01."+side]
        ankle=bones["foot."+side]
        target=anchors[side]+Vector(offset)
        origin=hip.head.copy()
        first=(shin.head-origin).length
        second=(ankle.head-shin.head).length
        line=target-origin
        distance=min(line.length,first+second-.0003)
        direction=line.normalized()
        pole=(FORWARD-direction*FORWARD.dot(direction)).normalized()
        along=(first*first-second*second+distance*distance)/(2*distance)
        knee=origin+direction*along+pole*sqrt(max(0,first*first-along*along))
        point(hip,shin,knee-origin)
        point(shin,ankle,target-shin.head)
        world_rotation(ankle,Quaternion(SIDE,-offset[2]*1.7) @ soles[side])

    def arm(side,amount,accent):
        sign=1 if side=="L" else -1
        b=lambda name:bones[name+"."+side]
        # Let the elbow lead the hand away from the at-rest pose.
        upper=Vector((sign*.115,.045,-.993)).lerp(Vector((sign*.14,-.30,-.943)),amount)
        lower=Vector((sign*.12,-.045,-.99)).lerp(Vector((-sign*.13,-.97,.17+accent*.15)),amount)
        point(b("upperarm01"),b("lowerarm01"),upper)
        point(b("lowerarm01"),b("wrist"),lower)
        wrist,middle=b("wrist"),b("finger3-1")
        direction=Vector((-sign*.045,-.07,-.996)).lerp(Vector((-sign*.14,-.982,.15+accent*.13)),amount)
        point(wrist,middle,direction)
        axis=(middle.head-wrist.head).normalized()
        palm=((b("finger2-1").head-wrist.head).cross(b("finger5-1").head-wrist.head)*sign).normalized()
        desired=Vector((sign*.24,-.24,.94))
        projected=(desired-axis*desired.dot(axis)).normalized()
        turn=atan2(axis.dot(palm.cross(projected)),palm.dot(projected))
        rotate(wrist,axis,turn*amount*.62)
        palm=((b("finger2-1").head-wrist.head).cross(b("finger5-1").head-wrist.head)*sign).normalized()
        for finger in range(1,6):
            for joint in range(1,2 if finger==1 else 3):
                digit=b(f"finger{finger}-{joint}")
                bend=digit.vector.normalized().cross(palm)
                if bend.length>.001:
                    curl=(.30-.21*amount)+.043*(finger-3)+.05*accent
                    rotate(digit,bend.normalized(),curl*(.68 if joint==1 else 1))

    def pose(root,left,right,arms,face):
        for bone in bones:
            bone.matrix_basis.identity()
            bone.rotation_mode="QUATERNION"
        update()
        shift(bones["root"],root)
        foot("L",left)
        foot("R",right)
        yaw,nod,tilt,expression=face
        rotate(bones["spine03"],UP,radians(yaw*.32))
        rotate(bones["spine01"],FORWARD,radians(tilt*.35))
        rotate(bones["neck01"],SIDE,radians(nod*.28))
        rotate(bones["head"],UP,radians(yaw*.68))
        rotate(bones["head"],SIDE,radians(nod*.72))
        rotate(bones["head"],FORWARD,radians(tilt*.65))
        arm("L",arms[0],arms[2])
        arm("R",arms[1],arms[2])
        for side in ("L","R"):
            shift(bones["levator05."+side],(0,-.0006*expression,.0025*expression))

    ground=(0,0,0)
    neutral=((0,0,-.010),ground,ground,(0,0,0),(0,0,0,0))
    listening=[
        (1,neutral),
        (18,((-.008,0,-.011),ground,ground,(.03,.01,0),(-5,2,-3,.12))),
        (36,((-.019,0,-.019),(.009,-.015,.020),ground,(.11,.09,0),(-13,3,-4,.25))),
        (49,((-.025,-.011,-.020),(.029,-.039,0),ground,(.17,.09,.1),(-17,-3,-4,.38))),
        (69,((.009,-.018,-.025),(.029,-.039,0),ground,(.23,.14,0),(-9,-3,-2,.30))),
        (102,((.028,-.019,-.020),(.029,-.039,0),ground,(.25,.18,.13),(7,5,5,.52))),
        (124,((.019,-.007,-.014),(.029,-.039,0),ground,(.10,.10,0),(13,4,4,.23))),
        (151,((-.008,.002,-.020),(.015,-.019,.018),ground,(.08,.07,.0),(4,-2,2,.15))),
        (165,((-.009,.002,-.016),ground,ground,(.05,.04,0),(0,0,1,.06))),
        (196,neutral),
    ]
    speaking=[
        (1,neutral),
        (12,((.012,-.008,-.014),ground,(-.011,-.017,.023),(.12,.17,-.12),(-5,4,-4,.45))),
        (25,((-.010,-.031,-.025),ground,(-.026,-.062,0),(.52,.62,.02),(-12,-6,-6,.85))),
        (40,((-.030,-.039,-.027),ground,(-.026,-.062,0),(.74,.84,.20),(2,3,-5,1))),
        (57,((-.023,-.035,-.025),ground,(-.026,-.062,0),(.29,.37,-.08),(13,-5,5,.64))),
        (76,((.009,-.021,-.022),(.010,-.027,.023),(-.026,-.062,0),(.13,.16,.02),(11,5,6,.77))),
        (92,((.026,-.018,-.024),(.017,-.047,0),(-.026,-.062,0),(.07,.10,.03),(-5,-3,1,.51))),
        (110,((.018,-.003,-.018),(.017,-.047,0),(-.014,-.028,.021),(.055,.06,0),(-8,3,-2,.22))),
        (126,((.008,-.003,-.019),(.009,-.017,.015),ground,(.13,.11,0),(-1,1,0,.10))),
        (140,neutral),
    ]
    data=rig.animation_data_create()
    actions={}
    for name,keys in (("Listening",listening),("Speaking",speaking)):
        action=bpy.data.actions.new(name)
        data.action=action
        for frame,parameters in keys:
            pose(*parameters)
            for name_of_bone in keyed:
                bone=bones[name_of_bone]
                bone.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=bone.name)
                if name_of_bone=="root" or name_of_bone.startswith("levator"):
                    bone.keyframe_insert(data_path="location",frame=frame,group=bone.name)
        actions[name]=action
        data.action=None
        track=data.nla_tracks.new()
        track.name=name
        track.strips.new(name,1,action)
        track.mute=True
    pose(*neutral)
    return actions
