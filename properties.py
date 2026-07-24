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
from abc import ABCMeta, abstractmethod
from . import bones
from . import strings

class IMocopiAvatarPropertyListener(metaclass=ABCMeta):

    @abstractmethod
    def on_rig_updated(self, context: bpy.types.Context, id: int, rig: str):
        pass

    @abstractmethod
    def on_bone_updated(self, context: bpy.types.Context, id: int, rig: str):
        pass

    @abstractmethod
    def on_debug_id_updated(self, context: bpy.types.Context, id: int, debug_id: int):
        pass

class MocopiAvatarProperty(bpy.types.PropertyGroup):

    listener: IMocopiAvatarPropertyListener = None

    def on_rig_updated(self, context):
        MocopiAvatarProperty.listener.on_rig_updated(context, self.id, self.rig)

    def on_bone_updated(self, context):
        MocopiAvatarProperty.listener.on_bone_updated(context, self.id, self.rig)

    def on_debug_id_updated(self, context):
        MocopiAvatarProperty.listener.on_debug_id_updated(context, self.id, self.debug_id)
 
    id: bpy.props.IntProperty(name='id')  # type: ignore Blenderの動的プロパティ
    
    port: bpy.props.IntProperty(name='port', default=12351)  # type: ignore Blenderの動的プロパティ

    rig: bpy.props.PointerProperty(name='rig', type=bpy.types.Object, update=on_rig_updated) # type: ignore Blenderの動的プロパティ

    root: bpy.props.StringProperty(name='root', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_1: bpy.props.StringProperty(name='torso_1', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_2: bpy.props.StringProperty(name='torso_2', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_3: bpy.props.StringProperty(name='torso_3', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_4: bpy.props.StringProperty(name='torso_4', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_5: bpy.props.StringProperty(name='torso_5', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_6: bpy.props.StringProperty(name='torso_6', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    torso_7: bpy.props.StringProperty(name='torso_7', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    neck_1: bpy.props.StringProperty(name='neck_1', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    neck_2: bpy.props.StringProperty(name='neck_2', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    head: bpy.props.StringProperty(name='head', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_shoulder: bpy.props.StringProperty(name='l_shoulder', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_up_arm: bpy.props.StringProperty(name='l_up_arm', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_low_arm: bpy.props.StringProperty(name='l_low_arm', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_hand: bpy.props.StringProperty(name='l_hand', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_shoulder: bpy.props.StringProperty(name='r_shoulder', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_up_arm: bpy.props.StringProperty(name='r_up_arm',  update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_low_arm: bpy.props.StringProperty(name='r_low_arm', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_hand: bpy.props.StringProperty(name='r_hand', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_up_leg: bpy.props.StringProperty(name='l_up_leg', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_low_leg: bpy.props.StringProperty(name='l_low_leg', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_foot: bpy.props.StringProperty(name='l_foot', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    l_toes: bpy.props.StringProperty(name='l_toes', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_up_leg: bpy.props.StringProperty(name='r_up_leg', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_low_leg: bpy.props.StringProperty(name='r_low_leg', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_foot: bpy.props.StringProperty(name='r_foot', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    r_toes: bpy.props.StringProperty(name='r_toes', update=on_bone_updated) # type: ignore Blenderの動的プロパティ

    mode: bpy.props.EnumProperty(
        name='mode',
        items=[
            ('v1', strings.get('legacy_mode'), strings.get('legacy_mode')),
            ('v2', strings.get('generic_mode'), strings.get('generic_mode')),
        ],
        default='v2'
    ) # type: ignore Blenderの動的プロパティ

    model_type: bpy.props.EnumProperty(
        name='model_type',
        items=[
            ('standard', strings.get('standard'), strings.get('standard')),
            ('mixamo', strings.get('mixamo'), strings.get('mixamo')),
        ]
    ) # type: ignore Blenderの動的プロパティ

    debug_id: bpy.props.IntProperty(name='debug_id', update=on_debug_id_updated)  # type: ignore Blenderの動的プロパティ

    def init(self):
        self.port = 12351
        self.rig = None
        self.root = ''
        self.torso_1 = ''
        self.torso_2 = ''
        self.torso_3 = ''
        self.torso_4 = ''
        self.torso_5 = ''
        self.torso_6 = ''
        self.torso_7 = ''
        self.neck_1 = ''
        self.neck_2 = ''
        self.head = ''
        self.l_shoulder = ''
        self.l_up_arm = ''
        self.l_low_arm = ''
        self.l_hand = ''
        self.r_shoulder = ''
        self.r_up_arm = ''
        self.r_low_arm = ''
        self.r_hand = ''
        self.l_up_leg = ''
        self.l_low_leg = ''
        self.l_foot = ''
        self.l_toes = ''
        self.r_up_leg = ''
        self.r_low_leg = ''
        self.r_foot = ''
        self.r_toes = ''

    def get_bone(self, bone_id: int) -> str:
        if bone_id == 0:
            return self.root
        elif bone_id == 1:
            return self.torso_1
        elif bone_id == 2:
            return self.torso_2
        elif bone_id == 3:
            return self.torso_3
        elif bone_id == 4:
            return self.torso_4
        elif bone_id == 5:
            return self.torso_5
        elif bone_id == 6:
            return self.torso_6
        elif bone_id == 7:
            return self.torso_7
        elif bone_id == 8:
            return self.neck_1
        elif bone_id == 9:
            return self.neck_2
        elif bone_id == 10:
            return self.head
        elif bone_id == 11:
            return self.l_shoulder
        elif bone_id == 12:
            return self.l_up_arm
        elif bone_id == 13:
            return self.l_low_arm
        elif bone_id == 14:
            return self.l_hand
        elif bone_id == 15:
            return self.r_shoulder
        elif bone_id == 16:
            return self.r_up_arm
        elif bone_id == 17:
            return self.r_low_arm
        elif bone_id == 18:
            return self.r_hand
        elif bone_id == 19:
            return self.l_up_leg
        elif bone_id == 20:
            return self.l_low_leg
        elif bone_id == 21:
            return self.l_foot
        elif bone_id == 22:
            return self.l_toes
        elif bone_id == 23:
            return self.r_up_leg
        elif bone_id == 24:
            return self.r_low_leg
        elif bone_id == 25:
            return self.r_foot
        elif bone_id == 26:
            return self.r_toes
        return None
    
    def get_bone_list(self) -> list[str]:
        return [
            self.root,
            self.torso_1,
            self.torso_2,
            self.torso_3,
            self.torso_4,
            self.torso_5,
            self.torso_6,
            self.torso_7,
            self.neck_1,
            self.neck_2,
            self.head,
            self.l_shoulder,
            self.l_up_arm,
            self.l_low_arm,
            self.l_hand,
            self.r_shoulder,
            self.r_up_arm,
            self.r_low_arm,
            self.r_hand,
            self.l_up_leg,
            self.l_low_leg,
            self.l_foot,
            self.l_toes,
            self.r_up_leg,
            self.r_low_leg,
            self.r_foot,
            self.r_toes
        ]

    def auto_retarget(self, rig: bpy.types.Object):

        if not rig or rig.type != 'ARMATURE':
            return
        
        self.root = self.__find_bone_name(rig.pose.bones, bones.ROOT_BONES)
        self.torso_1 = self.__find_bone_name(rig.pose.bones, bones.TORSO_1_BONES)
        self.torso_2 = self.__find_bone_name(rig.pose.bones, bones.TORSO_2_BONES)
        self.torso_3 = self.__find_bone_name(rig.pose.bones, bones.TORSO_3_BONES)
        self.torso_4 = self.__find_bone_name(rig.pose.bones, bones.TORSO_4_BONES)
        self.torso_5 = self.__find_bone_name(rig.pose.bones, bones.TORSO_5_BONES)
        self.torso_6 = self.__find_bone_name(rig.pose.bones, bones.TORSO_6_BONES)
        self.torso_7 = self.__find_bone_name(rig.pose.bones, bones.TORSO_7_BONES)
        self.neck_1 = self.__find_bone_name(rig.pose.bones, bones.NECK_1_BONES)
        self.neck_2 = self.__find_bone_name(rig.pose.bones, bones.NECK_2_BONES)
        self.head = self.__find_bone_name(rig.pose.bones, bones.HEAD_BONES)
        
        self.l_shoulder = self.__find_bone_name(rig.pose.bones, bones.SHOULDER_BONES, is_left=True)
        self.l_up_arm = self.__find_bone_name(rig.pose.bones, bones.UP_ARM_BONES, is_left=True)
        self.l_low_arm = self.__find_bone_name(rig.pose.bones, bones.LOW_ARM_BONES, is_left=True)
        self.l_hand = self.__find_bone_name(rig.pose.bones, bones.HAND_BONES, is_left=True)

        self.r_shoulder = self.__find_bone_name(rig.pose.bones, bones.SHOULDER_BONES)
        self.r_up_arm = self.__find_bone_name(rig.pose.bones, bones.UP_ARM_BONES)
        self.r_low_arm = self.__find_bone_name(rig.pose.bones, bones.LOW_ARM_BONES)
        self.r_hand = self.__find_bone_name(rig.pose.bones, bones.HAND_BONES)

        self.l_up_leg = self.__find_bone_name(rig.pose.bones, bones.UP_LEG_BONES, is_left=True)
        self.l_low_leg = self.__find_bone_name(rig.pose.bones, bones.LOW_LEG_BONES, is_left=True)
        self.l_foot = self.__find_bone_name(rig.pose.bones, bones.FOOT_BONES, is_left=True)
        self.l_toes = self.__find_bone_name(rig.pose.bones, bones.TOE_BONES, is_left=True)
        
        self.r_up_leg = self.__find_bone_name(rig.pose.bones, bones.UP_LEG_BONES)
        self.r_low_leg = self.__find_bone_name(rig.pose.bones, bones.LOW_LEG_BONES)
        self.r_foot = self.__find_bone_name(rig.pose.bones, bones.FOOT_BONES)
        self.r_toes = self.__find_bone_name(rig.pose.bones, bones.TOE_BONES)

    # Private

    def __find_bone_name(self, all_bone: list[bpy.types.PoseBone], keywords: list[str], is_left: bool = False) -> str:
        if not all_bone:
            return ''
        for w in keywords:
            bone = next((b for b in all_bone if w.lower() == b.name.lower()), None) # 完全一致
            if bone:
                return bone.name
        for w in keywords:
            w = w.lower()
            if '\l' in w:
                if is_left:
                    for key in ['l', 'left']:
                        w2 = w.replace('\l', key)
                        bone = next((b for b in all_bone if w2 .lower()== b.name.lower()), None) # 完全一致
                        if bone:
                            return bone.name
                else:
                    for key in ['r', 'right']:
                        w2 = w.replace('\l', key)
                        bone = next((b for b in all_bone if w2.lower() == b.name.lower()), None) # 完全一致
                        if bone:
                            return bone.name
            # else:
            #     bone = next((b for b in all_bone if w.lower() == b.name.lower()), None) # 完全一致
            #     return bone
        # for w in keywords:
            #     bone = next((b for b in all_bone if w.lower() in b.name.lower()), None) # 部分一致
            #     if bone:
            #         return bone.name
        return ''

class MocopiAvatarProperty_1(MocopiAvatarProperty):
    id: bpy.props.IntProperty(name='id', default=1) # type: ignore Blenderの動的プロパティ
    port: bpy.props.IntProperty(name='port', default=12351) # type: ignore Blenderの動的プロパティ


class MocopiAvatarProperty_2(MocopiAvatarProperty):
    id: bpy.props.IntProperty(name='id', default=2) # type: ignore Blenderの動的プロパティ
    port: bpy.props.IntProperty(name='port', default=12352) # type: ignore Blenderの動的プロパティ


class MocopiAvatarProperty_3(MocopiAvatarProperty):
    id: bpy.props.IntProperty(name='id', default=3) # type: ignore Blenderの動的プロパティ
    port: bpy.props.IntProperty(name='port', default=12353) # type: ignore Blenderの動的プロパティ

        
class MocopiProperty(bpy.types.PropertyGroup):
    avatar_1: bpy.props.PointerProperty(type=MocopiAvatarProperty_1) # type: ignore
    avatar_2: bpy.props.PointerProperty(type=MocopiAvatarProperty_2) # type: ignore
    avatar_3: bpy.props.PointerProperty(type=MocopiAvatarProperty_3) # type: ignore

    @classmethod
    def register(cls):
        scene = bpy.types.Scene
        scene.mocopi_property = bpy.props.PointerProperty(type=MocopiProperty)

    @classmethod
    def unregister(cls):
        scene = bpy.types.Scene
        if hasattr(scene, "mocopi_property"):
            del scene.mocopi_property

    def get(self, id: int) -> MocopiAvatarProperty:
        if id == 1:
            return self.avatar_1
        elif id == 2:
            return self.avatar_2
        elif id == 3:
            return self.avatar_3
        return None
