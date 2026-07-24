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

def resolve_armature(obj: bpy.types.Object) -> bpy.types.Object | None:
    if is_armature(obj):
        return obj
    if not is_valid(obj):
        return None

    # 親階層を辿ってアーマチュアを探す
    parent = obj.parent
    while is_valid(parent):
        if is_armature(parent):
            return parent
        parent = parent.parent

    # Armatureモディファイアから参照されるアーマチュアを探す
    for mod in getattr(obj, 'modifiers', []):
        if getattr(mod, 'type', None) == 'ARMATURE' and is_armature(getattr(mod, 'object', None)):
            return mod.object

    # Blender組み込みの探索結果も利用する
    try:
        found = obj.find_armature()
        if is_armature(found):
            return found
    except Exception:
        pass

    return None

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

def ensure_action_slot(anim_data: bpy.types.AnimData) -> None:
    """
    Blender 4.4+ の Slotted Actions 互換: action 割当後に slot が未設定なら明示設定する。
    """
    if not anim_data:
        return

    action = getattr(anim_data, 'action', None)
    if not action:
        return

    # Blender 4.3 以前は action_slot が存在しない
    if not hasattr(anim_data, 'action_slot'):
        return

    try:
        if anim_data.action_slot:
            return
    except Exception:
        return

    # まず Blender 側の適合候補から割り当て
    suitable_slots = getattr(anim_data, 'action_suitable_slots', None)
    if suitable_slots:
        try:
            anim_data.action_slot = suitable_slots[0]
            return
        except Exception:
            pass

    # 候補がない場合は action 側に slot を作成して再割り当てを試す
    slots = getattr(action, 'slots', None)
    id_owner = getattr(anim_data, 'id_data', None)
    if slots and id_owner and hasattr(id_owner, 'id_type'):
        try:
            slot = slots.new(id_type=id_owner.id_type, name=id_owner.name)
            anim_data.action_slot = slot
        except Exception:
            pass

def set_active_object(obj: bpy.types.Object) -> bool:
    if not is_valid(obj):
        return False
    view_layer = getattr(bpy.context, 'view_layer', None)
    if not view_layer:
        return False
    view_layer.objects.active = obj
    return view_layer.objects.active == obj

def ensure_object_mode(obj: bpy.types.Object, mode: str) -> bool:
    """
    指定オブジェクトをアクティブ化し、必要な場合のみ mode_set する。
    Blenderの内部トグル連打を減らしてモード遷移を安定させる。
    """
    if not set_active_object(obj):
        return False
    current_mode = getattr(obj, 'mode', None)
    if current_mode == mode:
        return True
    try:
        bpy.ops.object.mode_set(mode=mode)
    except Exception:
        return False
    return getattr(obj, 'mode', None) == mode

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
    if frame_start is None or frame_end is None:
        return
    frame_start, frame_end = int(frame_start), int(frame_end)
    if frame_end < frame_start:
        return

    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    if not ensure_object_mode(target_armature, 'POSE'):
        return

    target_anim_data = target_armature.animation_data_create()
    if not target_anim_data.action:
        target_anim_data.action = bpy.data.actions.new(name='mocopi_baked_action')
    ensure_action_slot(target_anim_data)

    wm = bpy.context.window_manager
    wm.progress_begin(0, 1)
    try:
        bpy.ops.nla.bake(
            frame_start=frame_start,
            frame_end=frame_end,
            visual_keying=True,
            only_selected=False,
            use_current_action=True,
            bake_types={'POSE'}
        )
        ensure_action_slot(target_anim_data)
    finally:
        wm.progress_end()

    ensure_object_mode(target_armature, 'OBJECT')

def read_anim_start_end(armature: bpy.types.Object) -> tuple:
    anim_data = getattr(armature, 'animation_data', None)
    action = getattr(anim_data, 'action', None)
    if not action:
        return None, None

    frame_range = getattr(action, 'frame_range', None)
    if frame_range and len(frame_range) >= 2:
        start = float(frame_range[0])
        end = float(frame_range[1])
        if end >= start:
            return start, end

    # 旧API互換のフォールバック
    fcurves = getattr(action, 'fcurves', None)
    if fcurves:
        frame_start = None
        frame_end = None
        for fcurve in fcurves:
            for key in fcurve.keyframe_points:
                keyframe = key.co.x
                if frame_start is None or keyframe < frame_start:
                    frame_start = keyframe
                if frame_end is None or keyframe > frame_end:
                    frame_end = keyframe
        return frame_start, frame_end

    return None, None