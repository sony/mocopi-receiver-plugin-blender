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
import threading
import asyncio
import socket
import struct
import errno
import math
import os
import time
from typing import List
from mathutils import Vector, Quaternion, Matrix
from . import properties
from . import utils

class BoneData:

    def __init__(self, bone_id: int):
        self.bone_id = bone_id
        self.bone: bpy.types.PoseBone = None


class Avatar:
    
    def __init__(self, id: int, panel_class: type):

        self.id = id
        self.panel_class = panel_class

        self.bone_data_list: List[BoneData] = []
        for bone_id in range(MocopiData.MAX_BONE): 
            self.bone_data_list.append(BoneData(bone_id))

        self.running: bool = False
        self.udp_socket: socket.socket = None
        self.thread: threading.Thread = None

        self.last_data: MocopiData = None
        self.last_packet_time: float = 0.0
        self.base_location: Vector = None
        self.updating: bool = False

        self.rig: bpy.types.Object = None

        # Ver1.0.0
        self.rig_scale: float = 1.0

        # Ver2.0.0
        self.skeleton: bpy.types.Object = None
        self.is_recording: bool = False
        self.retarget_base_rotation: Quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))

        self.debug_id: int = 0

    # Public

    def __get_scene(self) -> bpy.types.Scene:
        scene = bpy.context.scene
        if scene:
            return scene
        if bpy.data.scenes:
            return bpy.data.scenes[0]
        return None

    def update(self):

        if not self.running:
            return

        if not self.last_data:
            return

        scene = self.__get_scene()
        if not scene or not hasattr(scene, 'mocopi_property'):
            return

        prop: properties.MocopiAvatarProperty = scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop) or not utils.is_valid(self.rig):
            return
        
        # アクション
        if self.is_recording and (not self.rig.animation_data or not self.rig.animation_data.action):
            action_data = self.rig.animation_data_create()
            action_data.action = bpy.data.actions.new(name='mocopi_action')
            utils.ensure_action_slot(action_data)
        
        if prop.mode == 'v1':
        
            self.updating = True

            # ボーンの更新
            for bone_id in range(MocopiData.MAX_BONE):
                self.__bone_update(bone_id, self.rig , mode='v1')

            # アクション
            if self.is_recording:
                self.__action_update(self.rig)

        elif prop.mode == 'v2':
            
            self.updating = True

            # ボーンの更新
            for bone_id in range(MocopiData.MAX_BONE):
                self.__bone_update(bone_id, self.rig , mode='v2')

            view_layer = getattr(bpy.context, 'view_layer', None)
            if view_layer:
                view_layer.update()

            # アクション
            if self.is_recording:
                self.__action_update(self.skeleton)

        self.updating = False

    def retarget(self, rig: bpy.types.Object, prop: properties.MocopiAvatarProperty = None):
        self.rig = rig

        # v2 実行中は panel draw / timer sync で retarget() が再入しても、
        # 更新先を target rig に戻さず mocopiSkeleton を維持する。
        if self.running and prop and prop.mode == 'v2' and utils.is_armature(self.skeleton):
            self.__set_bone_data_list(self.skeleton)
            return

        self.__set_bone_data_list(rig, prop)

    def run(self):

        scene = self.__get_scene()
        if not scene or not hasattr(scene, 'mocopi_property'):
            return

        prop: properties.MocopiAvatarProperty = scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop) or not utils.is_armature(self.rig):
            return

        self.running = True
        self.base_location = None
        self.last_data = None
        self.last_packet_time = 0.0

        if prop.mode == 'v1':

            self.is_recording = True
            self.rig_scale = self.__get_scale_armature(self.rig) / utils.get_scale_value(self.rig)

            # bpy.context.view_layer.objects.active = self.rig
            # bpy.ops.object.mode_set(mode='POSE')

            # 非選択（オブジェクト選択中はupdateしないため）
            self.rig.select_set(False)

        if prop.mode == 'v2':

            self.is_recording = False
            self.rig_scale = 1.0

            # スケルトンの作成
            if utils.is_valid(self.skeleton):
                bpy.data.objects.remove(self.skeleton, do_unlink=True)
                self.skeleton = None
            self.skeleton = self.__create_skeleton()

            # リターゲット
            self.__set_bone_data_list(self.skeleton)
            if utils.is_armature(self.rig):
                self.__bake_retarget(prop, self.skeleton, self.rig)

            # bpy.context.view_layer.objects.active = self.skeleton
            # bpy.ops.object.mode_set(mode='POSE')

            # 非選択（オブジェクト選択中はupdateしないため）
            self.rig.select_set(False)
            self.skeleton.select_set(False)

            # 実行中は操作対象から外しつつ非表示にする
            self.skeleton.hide_set(True)
            self.skeleton.hide_select = True
            self.skeleton.display_type = 'WIRE'

        asyncio.run(self.__run())
        
    def stop(self):
        self.running = False
        self.last_data = None

        if self.udp_socket:
            self.udp_socket.close()
        self.udp_socket = None

        if self.thread:
            self.thread.join()
        self.thread = None

        scene = self.__get_scene()
        prop = scene.mocopi_property.get(self.id) if scene and hasattr(scene, 'mocopi_property') else None
        if utils.is_valid(prop) and prop.mode == 'v2':
            self.__bake_retarget_reset(prop, self.skeleton, self.rig)
            #self.rig.rotation_quaternion = self.t_base_quaternion.copy()

        if utils.is_valid(self.skeleton):
            bpy.data.objects.remove(self.skeleton, do_unlink=True)
            self.skeleton = None

        self.is_recording = False

    def start_recording(self):
        self.is_recording = True

    def stop_recording(self):
        
        self.is_recording = False

        scene = self.__get_scene()
        if not scene or not hasattr(scene, 'mocopi_property'):
            return

        prop: properties.MocopiAvatarProperty = scene.mocopi_property.get(self.id)
        self.__bake_animation(prop, self.skeleton, self.rig)

    def has_animation(self):
        return utils.is_armature(self.rig) and self.rig.animation_data and self.rig.animation_data.action

    # Private

    # Bake
    def __create_skeleton(self) -> bpy.types.Object:
        
        fbx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'skeleton.fbx')
        bpy.ops.import_scene.fbx(filepath=fbx_path)

        skeleton = bpy.context.active_object
        skeleton.name = f"mocopiSkeleton [{self.id}]"
        skeleton.rotation_mode = 'QUATERNION'

        action_data = skeleton.animation_data_create()
        action_data.action = bpy.data.actions.new(name=f"mocopiAction")
        utils.ensure_action_slot(action_data)
        return skeleton

    async def __run(self):

        scene = self.__get_scene()
        if not scene or not hasattr(scene, 'mocopi_property'):
            return

        prop: properties.MocopiAvatarProperty = scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop):
            return

        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # 同一PCプロセス(127.0.0.1)送信も受けるため全IFで待受する
            self.udp_socket.bind(('', prop.port))
            self.udp_socket.settimeout(5)
            print(f"mocopi_receiver: UDP listening (avatar={self.id}, port={prop.port})")

            self.thread = threading.Thread(target=self.__listen)
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            self.stop()

    def __listen(self):
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(4096) # 1024, 4096
                if data:
                    parsed = MocopiData(data)
                    if parsed.packet_type == 'frame':
                        self.last_data = parsed
                        self.last_packet_time = time.time()
                    elif parsed.packet_type == 'skeleton':
                        continue
            except socket.timeout:
                continue
            except OSError as e:
                # stop() 後の socket close に伴う想定内エラーは無視
                if not self.running and getattr(e, 'winerror', None) == 10038:
                    break
                if not self.running and getattr(e, 'errno', None) in (errno.EBADF, errno.ENOTSOCK):
                    break
                print(f"Error occurred: {e}")
            except (struct.error, UnicodeDecodeError, ValueError):
                continue
            except Exception as e:
                print(f"Error occurred: {e}")
    
    def __bone_update(self, bone_id: int, target_armature: bpy.types.Object, mode: str):

        scene = self.__get_scene()
        if not scene or not hasattr(scene, 'mocopi_property'):
            return

        prop: properties.MocopiAvatarProperty = scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop):
            return
        
        tran = self.last_data.get_tran(bone_id)
        if not tran:
            return
        
        bone = self.bone_data_list[bone_id].bone
        if not bone:
            return

        # 位置
        px = -tran[4]
        py =  tran[5]
        pz =  tran[6]

        # 回転
        qx = -tran[0]
        qy =  tran[1]
        qz =  tran[2]
        qw = -tran[3]

        # Root
        if bone_id == 0: # Root

            location = self.__get_position(px, py, pz, 4) # 4
            location *= self.rig_scale

            if not self.base_location:
                self.base_location = location
            bone.location = location - self.base_location

        # ボーンの回転
        bone.rotation_mode = 'QUATERNION'

        if mode == 'v1':
            if 11 <= bone_id and bone_id <= 13: # 左腕
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 77)
            elif bone_id == 14: # 左手首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 67)
            elif 15 <= bone_id and bone_id <= 17:# 右腕
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 70)
            elif bone_id == 18: # 右手首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 70)
            elif 19 <= bone_id and bone_id <= 21: # 左足
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 15)
            elif bone_id == 22: # 左足首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 17)
            elif 23 <= bone_id and bone_id <= 25:# 右足
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 0)
            elif bone_id == 26: # 右足首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 17)
            elif 8 <= bone_id and bone_id <= 10: # 首・顔
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 3)
            elif bone_id == 0: # Root
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 3)
            else: # その他
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 2)

        elif mode == 'v2':
            if 11 <= bone_id and bone_id <= 13: # 左腕
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 77)
            elif bone_id == 14: # 左手首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 39)
            elif 15 <= bone_id and bone_id <= 17:# 右腕
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 70)
            elif bone_id == 18: # 右手首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 36)
            elif 19 <= bone_id and bone_id <= 21: # 左足
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 15)
            elif bone_id == 22: # 左足首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 23)
            elif 23 <= bone_id and bone_id <= 25:# 右足
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 0)
            elif bone_id == 26: # 右足首
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 23)
            elif 8 <= bone_id and bone_id <= 10: # 首・顔
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 3)
            elif bone_id == 0: # Root
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 3)
            else: # その他
                bone.rotation_quaternion = self.__get_rotation(qw, qx, qy, qz, 2)

    def __action_update(self, rig: bpy.types.Object):

        if not rig.animation_data or not rig.animation_data.action:
            return

        utils.ensure_action_slot(rig.animation_data)

        scene = self.__get_scene()
        if not scene:
            return
        frame = scene.frame_current

        for bone_id in range(MocopiData.MAX_BONE):
            bone = self.bone_data_list[bone_id].bone
            if bone:
                if bone_id == 0:
                    bone.keyframe_insert(data_path="location", frame=frame, group=bone.name)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone.name)

        scene.frame_set(frame)

    def __set_bone_data_list(self, rig: bpy.types.Object, prop: properties.MocopiAvatarProperty = None):
        if utils.is_armature(rig):
            self.bone_data_list[0].bone = rig.pose.bones.get(prop.root if prop else utils.bone_id_to_bone_name(0))  
            self.bone_data_list[1].bone = rig.pose.bones.get(prop.torso_1 if prop else utils.bone_id_to_bone_name(1))
            self.bone_data_list[2].bone = rig.pose.bones.get(prop.torso_2 if prop else utils.bone_id_to_bone_name(2))
            self.bone_data_list[3].bone = rig.pose.bones.get(prop.torso_3 if prop else utils.bone_id_to_bone_name(3))
            self.bone_data_list[4].bone = rig.pose.bones.get(prop.torso_4 if prop else utils.bone_id_to_bone_name(4))
            self.bone_data_list[5].bone = rig.pose.bones.get(prop.torso_5 if prop else utils.bone_id_to_bone_name(5))
            self.bone_data_list[6].bone = rig.pose.bones.get(prop.torso_6 if prop else utils.bone_id_to_bone_name(6))
            self.bone_data_list[7].bone = rig.pose.bones.get(prop.torso_7 if prop else utils.bone_id_to_bone_name(7))
            self.bone_data_list[8].bone = rig.pose.bones.get(prop.neck_1 if prop else utils.bone_id_to_bone_name(8))
            self.bone_data_list[9].bone = rig.pose.bones.get(prop.neck_2 if prop else utils.bone_id_to_bone_name(9))
            self.bone_data_list[10].bone = rig.pose.bones.get(prop.head if prop else utils.bone_id_to_bone_name(10))
            self.bone_data_list[11].bone = rig.pose.bones.get(prop.l_shoulder if prop else utils.bone_id_to_bone_name(11))
            self.bone_data_list[12].bone = rig.pose.bones.get(prop.l_up_arm if prop else utils.bone_id_to_bone_name(12))
            self.bone_data_list[13].bone = rig.pose.bones.get(prop.l_low_arm if prop else utils.bone_id_to_bone_name(13))
            self.bone_data_list[14].bone = rig.pose.bones.get(prop.l_hand if prop else utils.bone_id_to_bone_name(14))
            self.bone_data_list[15].bone = rig.pose.bones.get(prop.r_shoulder if prop else utils.bone_id_to_bone_name(15))
            self.bone_data_list[16].bone = rig.pose.bones.get(prop.r_up_arm if prop else utils.bone_id_to_bone_name(16))
            self.bone_data_list[17].bone = rig.pose.bones.get(prop.r_low_arm if prop else utils.bone_id_to_bone_name(17))
            self.bone_data_list[18].bone = rig.pose.bones.get(prop.r_hand if prop else utils.bone_id_to_bone_name(18))
            self.bone_data_list[19].bone = rig.pose.bones.get(prop.l_up_leg if prop else utils.bone_id_to_bone_name(19))
            self.bone_data_list[20].bone = rig.pose.bones.get(prop.l_low_leg if prop else utils.bone_id_to_bone_name(20))
            self.bone_data_list[21].bone = rig.pose.bones.get(prop.l_foot if prop else utils.bone_id_to_bone_name(21))
            self.bone_data_list[22].bone = rig.pose.bones.get(prop.l_toes if prop else utils.bone_id_to_bone_name(22))
            self.bone_data_list[23].bone = rig.pose.bones.get(prop.r_up_leg if prop else utils.bone_id_to_bone_name(23))
            self.bone_data_list[24].bone = rig.pose.bones.get(prop.r_low_leg if prop else utils.bone_id_to_bone_name(24))
            self.bone_data_list[25].bone = rig.pose.bones.get(prop.r_foot if prop else utils.bone_id_to_bone_name(25))
            self.bone_data_list[26].bone = rig.pose.bones.get(prop.r_toes if prop else utils.bone_id_to_bone_name(26))

    # Bake
    def __bake_retarget(self, prop: properties.MocopiAvatarProperty, source_armature: bpy.types.Object, target_armature: bpy.types.Object):
        
        if not prop.root:
            return
        
        source_armature.hide_set(False)
        source_armature.select_set(True)
        target_armature.hide_set(False)
        target_armature.select_set(True)
        source_armature.rotation_mode = target_armature.rotation_mode = 'QUATERNION'

        # Transform合わせ
        source_armature.location = target_armature.location.copy()
        self.t_base_quaternion = target_armature.rotation_quaternion.copy()
        source_armature.rotation_quaternion = self.t_base_quaternion 


        if not utils.ensure_object_mode(target_armature, 'EDIT'):
            return

        # ヒップの向き補正計算
        source_hip_bone = source_armature.data.bones.get(utils.bone_id_to_bone_name(0))
        if not source_hip_bone:
            return
        source_forward = (source_hip_bone.tail_local - source_hip_bone.head_local).normalized()
        target_hip_edit_bone = target_armature.data.edit_bones.get(prop.get_bone(0))
        if not target_hip_edit_bone:
            return
        target_forward = (target_hip_edit_bone.tail - target_hip_edit_bone.head).normalized()
        hip_rotation = source_forward.rotation_difference(target_forward)
        self.retarget_base_rotation = hip_rotation

        if not utils.ensure_object_mode(source_armature, 'EDIT'):
            return

        # source_armatureのボーンを再計算 
        bone_update_list = {}
        hip_align = hip_rotation
        for bone_id in range(MocopiData.MAX_BONE):

            source_bone_name = utils.bone_id_to_bone_name(bone_id)
            source_bone = source_armature.pose.bones.get(source_bone_name)
            source_edit_bone = source_armature.data.edit_bones.get(source_bone_name)

            if source_bone is None or source_edit_bone is None:
                continue

            if bone_id == 0:
                # ヒップの向き補正計算
                head1 = hip_align @ source_edit_bone.head
                length = (source_edit_bone.tail - source_edit_bone.head).length
                fwd = (hip_align @ source_forward)
                tail1 = head1 + fwd * length
                bone_update_list[bone_id] = {
                    'head': head1,
                    'tail': tail1,
                    'roll': utils.mat3_to_vec_roll(hip_align.to_matrix() @ source_edit_bone.matrix.to_3x3())
                }
            else: 
                # head/tailを原点中心でhip_diff_quatだけ回転させる（寝てるのを起こす感じ）
                head0 = source_edit_bone.head.copy()
                tail0 = source_edit_bone.tail.copy()
                head1 = hip_align @ head0
                tail1 = hip_align @ tail0
                bone_update_list[bone_id] = {
                    'head': head1,
                    'tail': tail1,
                    'roll': utils.mat3_to_vec_roll(hip_align.to_matrix() @ source_edit_bone.matrix.to_3x3())
                }

        pending_constraints = []

        # 擬似ボーンの生成
        for bone_id in range(MocopiData.MAX_BONE):

            source_bone_name = utils.bone_id_to_bone_name(bone_id)
            source_bone = source_armature.pose.bones.get(source_bone_name)
            source_edit_bone = source_armature.data.edit_bones.get(source_bone_name)

            if source_edit_bone is None or bone_id not in bone_update_list:
                continue

            source_edit_bone.head = bone_update_list[bone_id]['head']
            source_edit_bone.tail = bone_update_list[bone_id]['tail']
            source_edit_bone.roll = bone_update_list[bone_id]['roll']

            target_bone_name = prop.get_bone(bone_id)
            if not target_bone_name:
                continue

            target_edit_bone = target_armature.data.edit_bones.get(target_bone_name) 
            if not target_edit_bone:
                continue

            new_source_edit_bone_name = target_bone_name
            if source_bone_name == new_source_edit_bone_name:
                # sourceとtargetのボーン名が同じ場合は接頭辞を付与
                new_source_edit_bone_name = '_' + new_source_edit_bone_name

            new_source_edit_bone = source_armature.data.edit_bones.get(new_source_edit_bone_name) 
            if new_source_edit_bone:
                source_armature.data.edit_bones.remove(new_source_edit_bone)

            new_source_edit_bone = source_armature.data.edit_bones.new(new_source_edit_bone_name)
            new_source_edit_bone.parent = source_edit_bone

            head = target_armature.matrix_world @ target_edit_bone.head
            tail = target_armature.matrix_world @ target_edit_bone.tail

            new_source_edit_bone.head = source_armature.matrix_world.inverted() @ head
            new_source_edit_bone.tail = source_armature.matrix_world.inverted() @ tail
            new_source_edit_bone.roll = utils.mat3_to_vec_roll(
                (source_armature.matrix_world.inverted().to_3x3() @ target_armature.matrix_world.to_3x3()) @ target_edit_bone.matrix.to_3x3()
            )

            pending_constraints.append((bone_id, target_bone_name, new_source_edit_bone_name))


        if not utils.ensure_object_mode(source_armature, 'OBJECT'):
            return

        if not utils.ensure_object_mode(target_armature, 'POSE'):
            return

        for bone_id, target_bone_name, subtarget_name in pending_constraints:
            target_bone = target_armature.pose.bones.get(target_bone_name)
            source_pose_bone = source_armature.pose.bones.get(subtarget_name)
            if not target_bone or not source_pose_bone:
                continue

            for constraint in list(target_bone.constraints):
                if constraint.name in {'mocopi_copy_location', 'mocopi_copy_rotation'}:
                    target_bone.constraints.remove(constraint)

            if bone_id == 0:
                constraint = target_bone.constraints.new('COPY_LOCATION')
                constraint.name = 'mocopi_copy_location'
                constraint.target = source_armature
                constraint.subtarget = subtarget_name
                constraint.target_space = 'WORLD'
                constraint.owner_space = 'WORLD'

            constraint = target_bone.constraints.new('COPY_ROTATION')
            constraint.name = 'mocopi_copy_rotation'
            constraint.target = source_armature
            constraint.subtarget = subtarget_name
            constraint.target_space = 'POSE'
            constraint.owner_space = 'POSE'

        if not utils.ensure_object_mode(source_armature, 'OBJECT'):
            return

        # 初期Transformだけ合わせ、常時のオブジェクト制約は張らない。
        # ターゲット骨 -> source骨 と sourceオブジェクト -> targetオブジェクト を同時に張ると
        # Blender 4.5 で評価循環になり、停止時だけ1フレーム見える状態になりやすい。
        for constraint in list(source_armature.constraints):
            if constraint.name in {'mocopi_obj_copy_location', 'mocopi_obj_copy_rotation'}:
                source_armature.constraints.remove(constraint)

        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')

        source_armature.hide_set(True)
        source_armature.hide_select = True
        source_armature.display_type = 'WIRE'
        source_armature.select_set(False)
        target_armature.hide_set(False)
        target_armature.select_set(False)

    def __bake_retarget_reset(self, prop: properties.MocopiAvatarProperty, source_armature: bpy.types.Object, target_armature: bpy.types.Object):

        target_armature.rotation_quaternion = self.t_base_quaternion.copy()

        if not utils.ensure_object_mode(source_armature, 'EDIT'):
            return

        for bone_id in range(MocopiData.MAX_BONE):

            target_bone_name = prop.get_bone(bone_id)
            if not target_bone_name:
                continue
            target_bone = target_armature.pose.bones.get(target_bone_name)

            for subtarget_name in (target_bone_name, f"_{target_bone_name}"):
                new_source_edit_bone = source_armature.data.edit_bones.get(subtarget_name)
                if new_source_edit_bone:
                    source_armature.data.edit_bones.remove(new_source_edit_bone)
            
            if target_bone.constraints:
                for constraint in list(target_bone.constraints):
                    if constraint.name in {'mocopi_copy_location', 'mocopi_copy_rotation'}:
                        target_bone.constraints.remove(constraint)

        for constraint in list(source_armature.constraints):
            if constraint.name in {'mocopi_obj_copy_location', 'mocopi_obj_copy_rotation'}:
                source_armature.constraints.remove(constraint)

        utils.ensure_object_mode(target_armature, 'OBJECT')
        bpy.context.view_layer.update()

    # Bake
    def __bake_animation(self, prop: properties.MocopiAvatarProperty, source_armature: bpy.types.Object, target_armature: bpy.types.Object):

        if not prop.root:
            return

        frame_start, frame_end = utils.read_anim_start_end(self.skeleton)
        if frame_start is None or frame_end is None:
            return

        target_armature.rotation_quaternion = self.t_base_quaternion.copy()

        source_armature.hide_set(False)
        source_armature.select_set(True)
        target_armature.hide_set(False)
        target_armature.select_set(True)

        # Default（設定）
        defaults = {
            'use_connect': False,
        }

        if not utils.ensure_object_mode(source_armature, 'EDIT'):
            return

        hip_target_bone_name = prop.get_bone(0)
        hip_target_edit_bone = target_armature.data.edit_bones.get(hip_target_bone_name)
        defaults['use_connect'] = hip_target_edit_bone.use_connect
        hip_target_edit_bone.use_connect = False

        # アニメーションのベイク
        if not utils.ensure_object_mode(source_armature, 'OBJECT'):
            return
        bpy.ops.object.select_all(action='DESELECT')
        
        # ベイク実行
        utils.bake_animation(self.skeleton, target_armature, target_bone_name_list=prop.get_bone_list())

        # Default（リセット）
        if not utils.ensure_object_mode(target_armature, 'EDIT'):
            return

        hip_target_edit_bone = target_armature.data.edit_bones.get(hip_target_bone_name)
        hip_target_edit_bone.use_connect = defaults['use_connect']

        if not utils.ensure_object_mode(target_armature, 'OBJECT'):
            return
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        source_armature.hide_set(True)
        source_armature.select_set(False)
        target_armature.hide_set(False)
        target_armature.select_set(False)
    
    def __get_scale_armature(self, source_armature: bpy.types.Object, target_armature: bpy.types.Object = None, prop: properties.MocopiAvatarProperty = None) -> float:

        # Easy
        if not target_armature or not prop:

            bone_min = None
            bone_min_root = None

            if not self.bone_data_list[0].bone:
                return 1.0

            for data in self.bone_data_list:

                if not data.bone:
                    continue

                bone_z = (source_armature.matrix_world @ data.bone.head)[2]
                if data.bone.name == self.bone_data_list[0].bone.name:
                    if not bone_min_root or bone_min_root > bone_z:
                        bone_min_root = bone_z
                if not bone_min or bone_min > bone_z:
                    bone_min = bone_z

            if not bone_min_root or not bone_min:
                return 1.0
            
            height = bone_min_root - bone_min
            if height == 0:
                return 1.0

            scale_factor = height / 0.899717666208744
            return scale_factor

        # Bake
        source_min = None
        source_min_root = None
        target_min = None
        target_min_root = None

        for bone_id in range(MocopiData.MAX_BONE):

            source_bone_name = utils.bone_id_to_bone_name(bone_id)
            source_bone = source_armature.pose.bones.get(source_bone_name)

            target_bone_name = prop.get_bone(bone_id)
            target_bone = target_armature.pose.bones.get(target_bone_name)

            if not source_bone or not target_bone:
                if bone_id == 0:
                    return 1.0
                continue

            bone_source_z = (source_armature.matrix_world @ source_bone.head)[2]
            bone_target_z = (target_armature.matrix_world @ target_bone.head)[2]

            if bone_id == 0:
                if not source_min_root or source_min_root > bone_source_z:
                    source_min_root = bone_source_z
                if not target_min_root or target_min_root > bone_target_z:
                    target_min_root = bone_target_z

            if not source_min or source_min > bone_source_z:
                source_min = bone_source_z
            if not target_min or target_min > bone_target_z:
                target_min = bone_target_z

        source_height = source_min_root - source_min
        target_height = target_min_root - target_min

        if not source_height or not target_height:
            return 1.0

        scale_factor = target_height / source_height
        return scale_factor
    
    def __get_position(self, px: float, py: float, pz: float, id: int) -> Vector:
        position = Vector((px, py, pz))
        if id == 0:
            position = Vector((px, py, pz))
        elif id == 1:
            position = Vector((px, -py, pz))
        elif id == 2:
            position = Vector((px, py, -pz))
        elif id == 3:
            position = Vector((px, -py, -pz))
        elif id == 4:
            position = Vector((-px, py, pz))
        elif id == 5:
            position = Vector((-px, -py, pz))
        elif id == 6:
            position = Vector((-px, py, -pz))
        elif id == 7:
            position = Vector((-px, -py, -pz))

        elif id == 8:
            position = Vector((px, pz, py))
        elif id == 9:
            position = Vector((px, -pz, py))
        elif id == 10:
            position = Vector((px, pz, -py))
        elif id == 11:
            position = Vector((px, -pz, -py))
        elif id == 12:
            position = Vector((-px, pz, py))
        elif id == 13:
            position = Vector((-px, -pz, py))
        elif id == 14:
            position = Vector((-px, pz, -py))
        elif id == 15:
            position = Vector((-px, -pz, -py))

        elif id == 16:
            position = Vector((py, px, pz))
        elif id == 17:
            position = Vector((py, -px, pz))
        elif id == 18:
            position = Vector((py, px, -pz))
        elif id == 19:
            position = Vector((py, -px, -pz))
        elif id == 20:
            position = Vector((-py, px, pz))
        elif id == 21:
            position = Vector((-py, -px, pz))
        elif id == 22:
            position = Vector((-py, px, -pz))
        elif id == 23:
            position = Vector((-py, -px, -pz))

        elif id == 24:
            position = Vector((py, pz, px))
        elif id == 25:
            position = Vector((py, -pz, px))
        elif id == 26:
            position = Vector((py, pz, -px))
        elif id == 27:
            position = Vector((py, -pz, -px))
        elif id == 28:
            position = Vector((-py, pz, px))
        elif id == 29:
            position = Vector((-py, -pz, px))
        elif id == 30:
            position = Vector((-py, pz, -px))
        elif id == 31:
            position = Vector((-py, -pz, -px))

        elif id == 32:
            position = Vector((pz, px, py))
        elif id == 33:
            position = Vector((pz, -px, py))
        elif id == 34:
            position = Vector((pz, px, -py))
        elif id == 35:
            position = Vector((pz, -px, -py))
        elif id == 36:
            position = Vector((-pz, px, py))
        elif id == 37:
            position = Vector((-pz, -px, py))
        elif id == 38:
            position = Vector((-pz, px, -py))
        elif id == 39:
            position = Vector((-pz, -px, -py))

        elif id == 40:
            position = Vector((pz, py, px))
        elif id == 41:
            position = Vector((pz, -py, px))
        elif id == 42:
            position = Vector((pz, py, -px))
        elif id == 43:
            position = Vector((pz, -py, -px))
        elif id == 44:
            position = Vector((-pz, py, px))
        elif id == 45:
            position = Vector((-pz, -py, px))
        elif id == 46:
            position = Vector((-pz, py, -px))
        elif id == 47:
            position = Vector((-pz, -py, -px))

        return position
    
    def __get_rotation(self, qw: float, qx: float, qy: float, qz: float, id: int) -> Quaternion:
        rotation = Quaternion([qw, qx, qy, qz])
        if (id == 0):
            rotation = Quaternion([qw, qx, qy, qz])
        elif (id == 1):
            rotation = Quaternion([qw, qx, -qy, qz])
        elif (id == 2):
            rotation = Quaternion([qw, qx, qy, -qz])
        elif (id == 3):
            rotation = Quaternion([qw, qx, -qy, -qz])
        elif (id == 4):
            rotation = Quaternion([qw, -qx, qy, qz])
        elif (id == 5):
            rotation = Quaternion([qw, -qx, -qy, qz])
        elif (id == 6):
            rotation = Quaternion([qw, -qx, qy, -qz])
        elif (id == 7):
            rotation = Quaternion([qw, -qx, -qy, -qz])

        elif (id == 8):
            rotation = Quaternion([-qw, qx, qy, qz])
        elif (id == 9):
            rotation = Quaternion([-qw, qx, -qy, qz])
        elif (id == 10):
            rotation = Quaternion([-qw, qx, qy, -qz])
        elif (id == 11):
            rotation = Quaternion([-qw, qx, -qy, -qz])
        elif (id == 12):
            rotation = Quaternion([-qw, -qx, qy, qz])
        elif (id == 13):
            rotation = Quaternion([-qw, -qx, -qy, qz])
        elif (id == 14):
            rotation = Quaternion([-qw, -qx, qy, -qz])
        elif (id == 15):
            rotation = Quaternion([-qw, -qx, -qy, -qz])

        elif (id == 16):
            rotation = Quaternion([qw, qx, qz, qy])
        elif (id == 17):
            rotation = Quaternion([qw, qx, -qz, qy])
        elif (id == 18):
            rotation = Quaternion([qw, qx, qz, -qy])
        elif (id == 19):
            rotation = Quaternion([qw, qx, -qz, -qy])
        elif (id == 20):
            rotation = Quaternion([qw, -qx, qz, qy])
        elif (id == 21):
            rotation = Quaternion([qw, -qx, -qz, qy])
        elif (id == 22):
            rotation = Quaternion([qw, -qx, qz, -qy])
        elif (id == 23):
            rotation = Quaternion([qw, -qx, -qz, -qy])
        
        elif (id == 24):
            rotation = Quaternion([-qw, qx, qz, qy])
        elif (id == 25):
            rotation = Quaternion([-qw, qx, -qz, qy])
        elif (id == 26):
            rotation = Quaternion([-qw, qx, qz, -qy])
        elif (id == 27):
            rotation = Quaternion([-qw, qx, -qz, -qy])
        elif (id == 28):
            rotation = Quaternion([-qw, -qx, qz, qy])
        elif (id == 29):
            rotation = Quaternion([-qw, -qx, -qz, qy])
        elif (id == 30):
            rotation = Quaternion([-qw, -qx, qz, -qy])
        elif (id == 31):
            rotation = Quaternion([-qw, -qx, -qz, -qy])

        if (id == 32):
            rotation = Quaternion([qw, qy, qx, qz])
        elif (id == 33):
            rotation = Quaternion([qw, -qy, qx, qz])
        elif (id == 34):
            rotation = Quaternion([qw, -qy, -qx, qz])
        elif (id == 35):
            rotation = Quaternion([qw, -qy, qx, -qz])
        elif (id == 36):
            rotation = Quaternion([qw, -qy, -qx, -qz])
        elif (id == 37):
            rotation = Quaternion([qw, qy, -qx, qz])
        elif (id == 38):
            rotation = Quaternion([qw, qy, -qx, -qz])
        elif (id == 39):
            rotation = Quaternion([qw, qy, qx, -qz])

        elif (id == 40):
            rotation = Quaternion([-qw, qy, qx, qz])
        elif (id == 41):
            rotation = Quaternion([-qw, -qy, qx, qz])
        elif (id == 42):
            rotation = Quaternion([-qw, -qy, -qx, qz])
        elif (id == 43):
            rotation = Quaternion([-qw, -qy, qx, -qz])
        elif (id == 44):
            rotation = Quaternion([-qw, -qy, -qx, -qz])
        elif (id == 45):
            rotation = Quaternion([-qw, qy, -qx, qz])
        elif (id == 46):
            rotation = Quaternion([-qw, qy, -qx, -qz])
        elif (id == 47):
            rotation = Quaternion([-qw, qy, qx, -qz])

        elif (id == 48):
            rotation = Quaternion([qw, qy, qz, qx])
        elif (id == 49):
            rotation = Quaternion([qw, -qy, qz, qx])
        elif (id == 50):
            rotation = Quaternion([qw, -qy, -qz, qx])
        elif (id == 51):
            rotation = Quaternion([qw, -qy, qz, -qx])
        elif (id == 52):
            rotation = Quaternion([qw, -qy, -qz, -qx])
        elif (id == 53):
            rotation = Quaternion([qw, qy, -qz, qx])
        elif (id == 54):
            rotation = Quaternion([qw, qy, -qz, -qx])
        elif (id == 55):
            rotation = Quaternion([qw, qy, qz, -qx])

        elif (id == 56):
            rotation = Quaternion([-qw, qy, qz, qx])
        elif (id == 57):
            rotation = Quaternion([-qw, -qy, qz, qx])
        elif (id == 58):
            rotation = Quaternion([-qw, -qy, -qz, qx])
        elif (id == 59):
            rotation = Quaternion([-qw, -qy, qz, -qx])
        elif (id == 60):
            rotation = Quaternion([-qw, -qy, -qz, -qx])
        elif (id == 61):
            rotation = Quaternion([-qw, qy, -qz, qx])
        elif (id == 62):
            rotation = Quaternion([-qw, qy, -qz, -qx])
        elif (id == 63):
            rotation = Quaternion([-qw, qy, qz, -qx])

        elif (id == 64):
            rotation = Quaternion([qw, qz, qx, qy])
        elif (id == 65):
            rotation = Quaternion([qw, -qz, qx, qy])
        elif (id == 66):
            rotation = Quaternion([qw, -qz, -qx, qy])
        elif (id == 67):
            rotation = Quaternion([qw, -qz, qx, -qy])
        elif (id == 68):
            rotation = Quaternion([qw, -qz, -qx, -qy])
        elif (id == 69):
            rotation = Quaternion([qw, qz, -qx, qy])
        elif (id == 70):
            rotation = Quaternion([qw, qz, -qx, -qy])
        elif (id == 71):
            rotation = Quaternion([qw, qz, qx, -qy])

        elif (id == 72):
            rotation = Quaternion([-qw, qz, qx, qy])
        elif (id == 73):
            rotation = Quaternion([-qw, -qz, qx, qy])
        elif (id == 74):
            rotation = Quaternion([-qw, -qz, -qx, qy])
        elif (id == 75):
            rotation = Quaternion([-qw, -qz, qx, -qy])
        elif (id == 76):
            rotation = Quaternion([-qw, -qz, -qx, -qy])
        elif (id == 77):
            rotation = Quaternion([-qw, qz, -qx, qy])
        elif (id == 78):
            rotation = Quaternion([-qw, qz, -qx, -qy])
        elif (id == 79):
            rotation = Quaternion([-qw, qz, qx, -qy])

        elif (id == 80):
            rotation = Quaternion([qw, qz, qy, qx])
        elif (id == 81):
            rotation = Quaternion([qw, -qz, qy, qx])
        elif (id == 82):
            rotation = Quaternion([qw, -qz, -qy, qx])
        elif (id == 83):
            rotation = Quaternion([qw, -qz, qy, -qx])
        elif (id == 84):
            rotation = Quaternion([qw, -qz, -qy, -qx])
        elif (id == 85):
            rotation = Quaternion([qw, qz, -qy, qx])
        elif (id == 86):
            rotation = Quaternion([qw, qz, -qy, -qx])
        elif (id == 87):
            rotation = Quaternion([qw, qz, qy, -qx])

        elif (id == 88):
            rotation = Quaternion([-qw, qz, qy, qx])
        elif (id == 89):
            rotation = Quaternion([-qw, -qz, qy, qx])
        elif (id == 90):
            rotation = Quaternion([-qw, -qz, -qy, qx])
        elif (id == 91):
            rotation = Quaternion([-qw, -qz, qy, -qx])
        elif (id == 92):
            rotation = Quaternion([-qw, -qz, -qy, -qx])
        elif (id == 93):
            rotation = Quaternion([-qw, qz, -qy, qx])
        elif (id == 94):
            rotation = Quaternion([-qw, qz, -qy, -qx])
        elif (id == 95):
            rotation = Quaternion([-qw, qz, qy, -qx])

        return rotation

class MocopiData:

    MAX_BONE = 27

    def __init__(self, data):

        self.head = {}
        self.sndf = {}
        self.fram = {}
        self.btrs = {}
        self.packet_type: str = 'unknown'

        self.__parse_packet(data)

    def get_tran(self, bone_id: int) -> list[float]:
        # return self.btrs['btdt'][bone_id]['tran']['data']

        btdt = next((btdt for btdt in self.btrs['btdt'] if btdt['bnid']['data'] == bone_id), None)
        return btdt['tran']['data'] if btdt else None

    def __parse_packet(self, packet: bytes):

        packet_len = len(packet)
        if packet_len < 8:
            raise ValueError('packet too short')

        head = self.__find_child(packet, 0, packet_len, 'head')
        if not head:
            raise ValueError('missing head chunk')

        self.head = self.__chunk_to_dict(head)

        ftyp = self.__find_child(packet, head['payload_start'], head['payload_end'], 'ftyp')
        if ftyp:
            self.head['ftyp'] = self.__chunk_to_dict(ftyp, self.__read_ascii(packet, ftyp))

        vrsn = self.__find_child(packet, head['payload_start'], head['payload_end'], 'vrsn')
        if vrsn:
            self.head['vrsn'] = self.__chunk_to_dict(vrsn, self.__read_int(packet, vrsn))

        sndf = self.__find_child(packet, 0, packet_len, 'sndf')
        if sndf:
            self.sndf = self.__chunk_to_dict(sndf)
            ipad = self.__find_child(packet, sndf['payload_start'], sndf['payload_end'], 'ipad')
            if ipad:
                self.sndf['ipad'] = self.__chunk_to_dict(ipad, self.__read_raw(packet, ipad))
            rcvp = self.__find_child(packet, sndf['payload_start'], sndf['payload_end'], 'rcvp')
            if rcvp:
                self.sndf['rcvp'] = self.__chunk_to_dict(rcvp, self.__read_raw(packet, rcvp))

        fram = self.__find_child(packet, 0, packet_len, 'fram')
        if fram:
            self.fram = self.__chunk_to_dict(fram)
            for key in ('fnum', 'time', 'uttm', 'tmcd'):
                child = self.__find_child(packet, fram['payload_start'], fram['payload_end'], key)
                if child:
                    self.fram[key] = self.__chunk_to_dict(child, self.__read_int(packet, child))

        btrs = self.__find_child(packet, 0, packet_len, 'btrs')
        skdf = self.__find_child(packet, 0, packet_len, 'skdf')

        # frame は fram / btrs 系チャンクを持つものだけを許可する
        has_frame_container = bool(fram or btrs)

        if btrs:
            self.btrs = self.__chunk_to_dict(btrs)
            btdt_chunks = self.__collect_chunks_recursive(packet, btrs['payload_start'], btrs['payload_end'], 'btdt')
        elif fram:
            # 送信側実装差分で btrs が省略されるケースに対応（fram内探索）
            self.btrs = {'size': 0, 'name': 'btrs', 'data': None, 'end': packet_len}
            btdt_chunks = self.__collect_chunks_recursive(packet, fram['payload_start'], fram['payload_end'], 'btdt')
        else:
            self.btrs = {'size': 0, 'name': 'btrs', 'data': None, 'end': packet_len}
            btdt_chunks = []

        btdt_list = []
        for chunk in btdt_chunks:
            bone = self.__parse_btdt(packet, chunk)
            if bone:
                btdt_list.append(bone)

        if not btdt_list and skdf:
                btdt_list = self.__parse_skdf_to_btdt(packet, skdf)
                if btdt_list:
                    self.packet_type = 'skeleton'

        if not btdt_list:
            top_names = ','.join(self.__list_chunk_names(packet, 0, packet_len))
            raise ValueError(f'missing btdt chunk (top={top_names})')

        if self.packet_type == 'unknown':
            if has_frame_container:
                self.packet_type = 'frame'
            elif skdf:
                self.packet_type = 'skeleton'
            else:
                top_names = ','.join(self.__list_chunk_names(packet, 0, packet_len))
                raise ValueError(f'unknown packet type (top={top_names})')

        self.btrs['btdt'] = btdt_list

    def __chunk_to_dict(self, chunk: dict, data=None) -> dict:
        return {
            'size': chunk['size'],
            'name': chunk['name'],
            'data': data,
            'end': chunk['end'],
        }

    def __read_chunk_header(self, packet: bytes, i: int, limit: int = None) -> dict:
        if i + 8 > len(packet):
            raise ValueError('invalid chunk header')

        size = int.from_bytes(packet[i:i+4], 'little')
        try:
            name = packet[i+4:i+8].decode('ascii')
        except UnicodeDecodeError as e:
            raise ValueError('invalid chunk name') from e
        payload_start = i + 8
        payload_end = payload_start + size

        boundary = len(packet) if limit is None else min(limit, len(packet))
        if payload_end > boundary:
            raise ValueError('chunk exceeds packet boundary')

        return {
            'size': size,
            'name': name,
            'start': i,
            'payload_start': payload_start,
            'payload_end': payload_end,
            'end': payload_end,
        }

    def __iter_children(self, packet: bytes, start: int, end: int):
        i = start
        while i + 8 <= end:
            chunk = self.__read_chunk_header(packet, i, end)
            yield chunk
            i = chunk['end']

    def __list_chunk_names(self, packet: bytes, start: int, end: int) -> list[str]:
        names = []
        try:
            for chunk in self.__iter_children(packet, start, end):
                names.append(chunk['name'])
        except ValueError:
            pass
        return names

    def __collect_chunks_recursive(self, packet: bytes, start: int, end: int, name: str, depth: int = 0, max_depth: int = 5) -> list[dict]:
        found = []
        if depth > max_depth:
            return found

        try:
            children = list(self.__iter_children(packet, start, end))
        except ValueError:
            return found

        for chunk in children:
            if chunk['name'] == name:
                found.append(chunk)

            # payloadがチャンク列でない場合は例外で自然に打ち切られる
            if chunk['size'] >= 8:
                found.extend(
                    self.__collect_chunks_recursive(
                        packet,
                        chunk['payload_start'],
                        chunk['payload_end'],
                        name,
                        depth + 1,
                        max_depth,
                    )
                )

        return found

    def __find_child(self, packet: bytes, start: int, end: int, name: str):
        for chunk in self.__iter_children(packet, start, end):
            if chunk['name'] == name:
                return chunk
        return None

    def __read_raw(self, packet: bytes, chunk: dict) -> bytes:
        return packet[chunk['payload_start']:chunk['payload_end']]

    def __read_ascii(self, packet: bytes, chunk: dict) -> str:
        return self.__read_raw(packet, chunk).decode('ascii')

    def __read_int(self, packet: bytes, chunk: dict) -> int:
        payload = self.__read_raw(packet, chunk)
        return int.from_bytes(payload, 'little') if payload else 0

    def __read_vector7(self, packet: bytes, chunk: dict) -> tuple:
        payload = self.__read_raw(packet, chunk)
        if len(payload) < 28:
            raise ValueError('tran chunk too short')
        count = len(payload) // 4
        values = struct.unpack('<' + ('f' * count), payload[:count * 4])
        return values[:7]

    def __parse_btdt(self, packet: bytes, btdt_chunk: dict):
        bnid_chunk = self.__find_child(packet, btdt_chunk['payload_start'], btdt_chunk['payload_end'], 'bnid')
        tran_chunk = self.__find_child(packet, btdt_chunk['payload_start'], btdt_chunk['payload_end'], 'tran')

        if not bnid_chunk or not tran_chunk:
            return None

        return {
            'size': btdt_chunk['size'],
            'name': btdt_chunk['name'],
            'bnid': self.__chunk_to_dict(bnid_chunk, self.__read_int(packet, bnid_chunk)),
            'tran': self.__chunk_to_dict(tran_chunk, self.__read_vector7(packet, tran_chunk)),
            'end': btdt_chunk['end'],
        }

    def __parse_skdf_to_btdt(self, packet: bytes, skdf_chunk: dict) -> list[dict]:
        bones_container = self.__find_child(packet, skdf_chunk['payload_start'], skdf_chunk['payload_end'], 'bons')
        if not bones_container:
            return []

        bndt_chunks = self.__collect_chunks_recursive(packet, bones_container['payload_start'], bones_container['payload_end'], 'bndt')
        btdt_list = []
        for bndt in bndt_chunks:
            bnid_chunk = self.__find_child(packet, bndt['payload_start'], bndt['payload_end'], 'bnid')
            tran_chunk = self.__find_child(packet, bndt['payload_start'], bndt['payload_end'], 'tran')
            if not bnid_chunk or not tran_chunk:
                continue

            btdt_list.append({
                'size': bndt['size'],
                'name': 'btdt',
                'bnid': self.__chunk_to_dict(bnid_chunk, self.__read_int(packet, bnid_chunk)),
                'tran': self.__chunk_to_dict(tran_chunk, self.__read_vector7(packet, tran_chunk)),
                'end': bndt['end'],
            })

        return btdt_list
