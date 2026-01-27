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
import math
import os
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

    def update(self):

        if not self.running or not self.last_data:
            return

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop) or not utils.is_valid(self.rig):
            return
        
        # アクション
        if self.is_recording and (not self.rig.animation_data or not self.rig.animation_data.action):
            action_data = self.rig.animation_data_create()
            action_data.action = bpy.data.actions.new(name='mocopi_action')
        
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

            # アクション
            if self.is_recording:
                self.__action_update(self.skeleton)

        self.updating = False

    def retarget(self, rig: bpy.types.Object, prop: properties.MocopiAvatarProperty = None):
        self.rig = rig
        self.__set_bone_data_list(rig, prop)

    def run(self):

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop) or not utils.is_armature(self.rig):
            return

        self.running = True
        self.base_location = None

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

            # スケルトンを非表示
            self.skeleton.hide_set(True)

        asyncio.run(self.__run())
        
    def stop(self):
        self.running = False

        if self.udp_socket:
            self.udp_socket.close()
        self.udp_socket = None

        if self.thread:
            self.thread.join()
        self.thread = None

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
        if prop.mode == 'v2':
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

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
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
        return skeleton

    async def __run(self):

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
        if not utils.is_valid(prop):
            return

        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', prop.port))
            self.udp_socket.settimeout(5)

            self.thread = threading.Thread(target=self.__listen)
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            self.stop()

    def __listen(self):
        while self.running:
            try:
                data, _ = self.udp_socket.recvfrom(4096) # 1024, 4096
                if data and not self.updating:
                    self.last_data = MocopiData(data)
            except socket.timeout:
                print("Error occurred: socket.timeout")
            except Exception as e:
                print(f"Error occurred: {e}")
    
    def __bone_update(self, bone_id: int, target_armature: bpy.types.Object, mode: str):

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)
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

        scene = bpy.context.scene
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


        bpy.context.view_layer.objects.active = target_armature
        bpy.ops.object.mode_set(mode='EDIT')

        # ヒップの向き補正計算
        source_hip_edit_bone = source_armature.data.edit_bones.get(utils.bone_id_to_bone_name(0))
        source_forward = (source_hip_edit_bone.tail - source_hip_edit_bone.head).normalized()
        target_hip_edit_bone = target_armature.data.edit_bones.get(prop.get_bone(0))
        target_forward = (target_hip_edit_bone.tail - target_hip_edit_bone.head).normalized()
        hip_rotation = source_forward.rotation_difference(target_forward)
        self.retarget_base_rotation = hip_rotation

        bpy.context.view_layer.objects.active = source_armature
        bpy.ops.object.mode_set(mode='EDIT')

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

        # 擬似ボーンの生成
        for bone_id in range(MocopiData.MAX_BONE):

            source_bone_name = utils.bone_id_to_bone_name(bone_id)
            source_bone = source_armature.pose.bones.get(source_bone_name)
            source_edit_bone = source_armature.data.edit_bones.get(source_bone_name)

            if source_edit_bone is None or bone_update_list[bone_id] is None:
                continue

            source_edit_bone.head = bone_update_list[bone_id]['head']
            source_edit_bone.tail = bone_update_list[bone_id]['tail']
            source_edit_bone.roll = bone_update_list[bone_id]['roll']

            target_bone_name = prop.get_bone(bone_id)
            if not target_bone_name:
                continue

            target_bone = target_armature.pose.bones.get(target_bone_name)
            target_edit_bone = target_armature.data.edit_bones.get(target_bone_name) 

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

            if target_bone.constraints:
                for constraint in filter(lambda c: c.type == 'COPY_LOCATION' or c.type == 'COPY_ROTATION', target_bone.constraints):
                    target_bone.constraints.remove(constraint)

            if bone_id == 0:
                constraint = target_bone.constraints.new('COPY_LOCATION')
                constraint.target = source_armature
                constraint.subtarget = target_bone_name
                constraint.target_space = 'WORLD'
                constraint.owner_space = 'WORLD'

            constraint = target_bone.constraints.new('COPY_ROTATION')
            constraint.target = source_armature
            constraint.subtarget = target_bone_name
            constraint.target_space = 'POSE'
            constraint.owner_space = 'POSE'


        # Transformの同期
        constraint = source_armature.constraints.get("Copy Location")
        constraint = source_armature.constraints.new(type='COPY_LOCATION')
        constraint.target = target_armature

        constraint = source_armature.constraints.new(type='COPY_ROTATION')
        constraint.target = target_armature
        constraint.use_offset = False
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        source_armature.hide_set(True)
        source_armature.select_set(False)
        target_armature.hide_set(False)
        target_armature.select_set(False)

    def __bake_retarget_reset(self, prop: properties.MocopiAvatarProperty, source_armature: bpy.types.Object, target_armature: bpy.types.Object):

        target_armature.rotation_quaternion = self.t_base_quaternion.copy()

        for bone_id in range(MocopiData.MAX_BONE):

            target_bone_name = prop.get_bone(bone_id)
            if not target_bone_name:
                continue
            target_bone = target_armature.pose.bones.get(target_bone_name)

            new_source_edit_bone = source_armature.data.edit_bones.get(target_bone_name) 
            if new_source_edit_bone:
                source_armature.data.edit_bones.remove(new_source_edit_bone) 
            
            if target_bone.constraints:
                for constraint in filter(lambda c: c.type == 'COPY_LOCATION' or c.type == 'COPY_ROTATION', target_bone.constraints):
                    target_bone.constraints.remove(constraint)

    # Bake
    def __bake_animation(self, prop: properties.MocopiAvatarProperty, source_armature: bpy.types.Object, target_armature: bpy.types.Object):

        if len(self.skeleton.animation_data.action.fcurves) == 0 or not prop.root:
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

        bpy.context.view_layer.objects.active = source_armature
        bpy.ops.object.mode_set(mode='EDIT')

        hip_target_bone_name = prop.get_bone(0)
        hip_target_edit_bone = target_armature.data.edit_bones.get(hip_target_bone_name)
        defaults['use_connect'] = hip_target_edit_bone.use_connect
        hip_target_edit_bone.use_connect = False

        # アニメーションのベイク
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        
        # ベイク実行
        utils.bake_animation(self.skeleton, target_armature, target_bone_name_list=prop.get_bone_list())

        # Default（リセット）
        bpy.context.view_layer.objects.active = target_armature

        bpy.ops.object.mode_set(mode='EDIT')

        hip_target_edit_bone = target_armature.data.edit_bones.get(hip_target_bone_name)
        hip_target_edit_bone.use_connect = defaults['use_connect']

        bpy.ops.object.mode_set(mode='OBJECT')
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

        self.__init(data)

    def get_tran(self, bone_id: int) -> list[float]:
        # return self.btrs['btdt'][bone_id]['tran']['data']

        btdt = next((btdt for btdt in self.btrs['btdt'] if btdt['bnid']['data'] == bone_id), None)
        return btdt['tran']['data'] if btdt else None

    def __init(self, data):
        
        i = 0

        # head
        head = self.__parse(data, i)
        i = head['end']

        # head > ftyp
        ftyp = self.__parse(data, i, 'ascii')
        i = ftyp['end']

        # head > vrsn
        vrsn = self.__parse(data, i, 'int')
        i = vrsn['end']

        self.head = head
        self.head['ftyp'] = ftyp
        self.head['vrsn'] = vrsn

        # sndf
        sndf = self.__parse(data, i)
        i = sndf['end']

        # sndf > ipad
        ipad = self.__parse(data, i, 'raw')
        i = ipad['end']

        # sndf > rcvp
        rcvp = self.__parse(data, i, 'raw')
        i = rcvp['end']

        self.sndf = sndf
        self.sndf['ipad'] = ipad
        self.sndf['rcvp'] = rcvp

        # fram
        fram = self.__parse(data, i)
        if fram['name'] == 'fram':
            i = fram['end']
            self.fram = fram

        # fram > fnum
        fnum = self.__parse(data, i, 'int')
        if fnum['name'] == 'fnum':
            i = fnum['end']
            self.fram['fnum'] = fnum

        # fram > time
        time = self.__parse(data, i, 'int')
        if time['name'] == 'time':
            i = time['end']
            self.fram['time'] = time

        # fram > uttm
        uttm = self.__parse(data, i, 'int')
        if uttm['name'] == 'uttm':
            i = uttm['end']
            self.fram['uttm'] = uttm

        # # fram > tmcd
        tmcd = self.__parse(data, i, 'int')
        if tmcd['name'] == 'tmcd':
            i = tmcd['end']
            self.fram['tmcd'] = tmcd

        # btrs
        btrs = self.__parse(data, i)
        i = btrs['end']

        # btrs > btdt
        btdt_list = []
        for _ in range(MocopiData.MAX_BONE):
            bone = self.__btdt_parse(data, i)
            i = bone['end']
            btdt_list.append(bone)

        self.btrs = btrs
        self.btrs['btdt'] = btdt_list
        
    def __parse(self, bytes: bytes, i: int, type: str = None) -> dict:

        SIZE = 4

        size = int.from_bytes(bytes[i:i+SIZE], 'little')
        i += SIZE
        name = bytes[i:i+SIZE].decode('ascii')
        i += SIZE

        data = None
        if type == 'ascii':
            data = bytes[i:i+size].decode('ascii')
            i += size
        elif type == 'int':
            data = int.from_bytes(bytes[i:i+size], 'little')
            i += size
        elif type == 'vector':
            data = struct.unpack('<7f', bytes[i:i+size])
            i += size
        elif type == 'raw':
            data = bytes[i:i+size]
            i += size
        
        return {
                'size': size, 
                'name': name, 
                'data': data, 
                'end': i
            }
    
    def __btdt_parse(self, bytes: bytes, i: int) -> dict:

        # btdt
        btdt = self.__parse(bytes, i)
        i = btdt['end']

        # btdt > bnid
        bnid = self.__parse(bytes, i, 'int')
        i = bnid['end']

        # btdt > tran
        tran = self.__parse(bytes, i, 'vector')
        i = tran['end']

        btdt['bnid'] = bnid
        btdt['tran'] = tran
        btdt['end'] = i

        return btdt    
