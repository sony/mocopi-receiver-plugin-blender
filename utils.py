###
# Copyright (C) 2026 Sony Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
###
import bpy
import socket
import math
from mathutils import Vector, Quaternion, Matrix

def is_valid(obj) -> bool:
    if not obj:
        return False
    try:
        _ = obj.name
    except ReferenceError:
        return False
    return True

def is_armature(obj: bpy.types.Object) -> bool:
    return is_valid(obj) and obj.type == 'ARMATURE'

def get_ip_address():
        ip_address = '127.0.0.1'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
        except Exception as e:
            pass
        return ip_address

def get_scale_value(obj: bpy.types.Object) -> float:
    if not is_valid(obj):
        return 1.0
    return (obj.scale.x + obj.scale.y + obj.scale.z) / 3.0

def get_bone_name(bone: bpy.types.PoseBone) -> str:
    try:
        if bone and isinstance(bone.name, bytes):
            return bone.name.decode('utf-8')
        return bone.name if bone else ''
    except (UnicodeDecodeError, AttributeError):
        return ''

def mat3_to_vec_roll(mat: Matrix) -> float:
    """
    3x3回転行列から、その行列が向けている方向ベクトルに対するロール角（ねじれ角）を算出して返す。
    - 行列のY列（col[1]）を向きベクトルとみなし、roll=0の基準回転を作る
    - 入力行列に対する相対回転を求め、そのZ軸まわり成分からロール角を取り出す
    """
    # 基準（roll=0）となる回転を作成（行列のY列を向ける）
    base_rot = vec_roll_to_mat3(mat.col[1], 0.0)

    # 入力行列を基準回転に対して相対化
    relative_rot = base_rot.inverted() @ mat

    # 相対回転のXZ成分からロール角を算出
    roll = math.atan2(relative_rot[0][2], relative_rot[2][2])
    return roll


def vec_roll_to_mat3(vec: Vector, roll: float) -> Matrix:
    """
    向きベクトル(vec)とロール角(roll)から3x3回転行列を生成して返す。
    - まず参照ベクトル(ほぼ+Y軸)をvecへ向ける回転を作る
    - その後、vecを軸としてroll分だけ回転させる
    """
    # 参照ベクトル（ゼロ除けのため長さ0.1）
    ref_y = Vector((0.0, 0.1, 0.0))

    # 向きベクトルを正規化
    direction = vec.normalized()

    # 参照ベクトルをdirectionへ回すための回転軸
    rot_axis = ref_y.cross(direction)

    if rot_axis.dot(rot_axis) > 1.0e-10:
        # 一般ケース：参照ベクトルとdirectionが非平行
        rot_axis.normalize()
        angle = ref_y.angle(direction)
        align_matrix = Matrix.Rotation(angle, 3, rot_axis)
    else:
        # 特殊ケース：参照ベクトルとdirectionがほぼ平行（クロス積が0）
        # 同向き: updown=+1, 逆向き: updown=-1
        updown = 1 if ref_y.dot(direction) > 0 else -1
        align_matrix = Matrix.Scale(updown, 3)
        align_matrix[2][2] = 1.0  # Zスケールは常に1に保つ

    # direction（向きベクトル）を回転軸に、roll分ひねる
    roll_matrix = Matrix.Rotation(roll, 3, direction)

    # まず参照ベクトルを目的方向へ合わせ、その後ロール回転を適用
    return roll_matrix @ align_matrix

def bone_id_to_bone_name(bone_id: int) -> str:
    if bone_id == 0:
        return 'root'
    elif bone_id == 1:
        return 'torso_1'
    elif bone_id == 2:
        return 'torso_2'
    elif bone_id == 3:
        return 'torso_3'
    elif bone_id == 4:
        return 'torso_4'
    elif bone_id == 5:
        return 'torso_5'
    elif bone_id == 6:
        return 'torso_6'
    elif bone_id == 7:
        return 'torso_7'
    elif bone_id == 8:
        return 'neck_1'
    elif bone_id == 9:
        return 'neck_2'
    elif bone_id == 10:
        return 'head'
    elif bone_id == 11:
        return 'l_shoulder'
    elif bone_id == 12:
        return 'l_up_arm'
    elif bone_id == 13:
        return 'l_low_arm'
    elif bone_id == 14:
        return 'l_hand'
    elif bone_id == 15:
        return 'r_shoulder'
    elif bone_id == 16:
        return 'r_up_arm'
    elif bone_id == 17:
        return 'r_low_arm'
    elif bone_id == 18:
        return 'r_hand'
    elif bone_id == 19:
        return 'l_up_leg'
    elif bone_id == 20:
        return 'l_low_leg'
    elif bone_id == 21:
        return 'l_foot'
    elif bone_id == 22:
        return 'l_toes'
    elif bone_id == 23:
        return 'r_up_leg'
    elif bone_id == 24:
        return 'r_low_leg'
    elif bone_id == 25:
        return 'r_foot'
    elif bone_id == 26:
        return 'r_toes'
    return ''

def bake_animation(source_armature: bpy.types.Object, target_armature: bpy.types.Object, target_bone_name_list: list[str], frame_split: int = 25):

    frame_start, frame_end = read_anim_start_end(source_armature)
    frame_start, frame_end = int(frame_start), int(frame_end)

    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    bpy.context.view_layer.objects.active = target_armature
    bpy.ops.object.mode_set(mode='POSE')

    target_action = target_armature.animation_data.action
    target_armature.animation_data.action = None

    split_ranges = list(range(frame_start, frame_end + 1, frame_split))
    if split_ranges[-1] != frame_end:
        split_ranges.append(frame_end)

    MAX_STEP = len(split_ranges) - 1
    wm = bpy.context.window_manager
    wm.progress_begin(0, MAX_STEP)

    all_actions = {}
    for step in range(MAX_STEP):

        start = split_ranges[step]
        end = split_ranges[step + 1]
        bpy.ops.nla.bake(frame_start=start, frame_end=end, visual_keying=True, only_selected=False, use_current_action=False, bake_types={'POSE'} )

        baked_action = target_armature.animation_data.action
        baked_action.name = f"baked_{start}_{end}"
        all_actions[(start, end)] = baked_action

        wm.progress_update(step)

    target_armature.animation_data.action = target_action
    target_action.use_fake_user = True

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)

        current_action = None
        for (start, end), action in all_actions.items():
            if start <= frame <= end:
                current_action = action
                break
        if current_action is None:
            continue
        
        for bone_name in target_bone_name_list:
            bone = target_armature.pose.bones.get(bone_name)
            if not bone:
                continue

            is_hip = bone_name == target_bone_name_list[0]
            if is_hip:
                loc = [0.0, 0.0, 0.0]
                for step in range(3):
                    fcurve = current_action.fcurves.find(f'pose.bones["{bone_name}"].location', index=step)
                    loc[step] = fcurve.evaluate(frame) if fcurve else loc[step]
                # Rootの回転を考慮してローカル座標に変換
                bone.location = Vector(loc) #target_armature.matrix_world.to_quaternion().inverted() @ Vector(loc)
                bone.keyframe_insert(data_path="location", frame=frame, group=bone_name)

            quat = [1.0, 0.0, 0.0, 0.0]
            for step in range(4):
                fcurve = current_action.fcurves.find(f'pose.bones["{bone_name}"].rotation_quaternion', index=step)
                quat[step] = fcurve.evaluate(frame) if fcurve else quat[step]
            bone.rotation_mode = 'QUATERNION'

            if is_hip:
                # Rootの回転を考慮してローカル回転に変換
                bone.rotation_quaternion = Quaternion(quat)#target_armature.matrix_world.to_quaternion().inverted() @ Quaternion(quat)
            else:
                bone.rotation_quaternion = Quaternion(quat)

            bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone_name)

    bpy.ops.object.mode_set(mode='OBJECT')

    for action in all_actions.values():
        bpy.data.actions.remove(action)

    wm.progress_end()

def read_anim_start_end(armature: bpy.types.Object) -> tuple:
    frame_start = None
    frame_end = None
    for fcurve in armature.animation_data.action.fcurves:
        for key in fcurve.keyframe_points:
            keyframe = key.co.x
            if not frame_start:
                frame_start = keyframe
            if not frame_end:
                frame_end = keyframe

            if keyframe < frame_start:
                frame_start = keyframe
            if keyframe > frame_end:
                frame_end = keyframe
    return frame_start, frame_end