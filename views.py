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
from . import main
from . import models
from . import properties
from . import utils
from . import strings

class IAvatarPanelListener(metaclass=ABCMeta):

    @abstractmethod
    def on_drawed(self, panel, context: bpy.types.Context, id: int) -> models.Avatar:
        pass

    @abstractmethod
    def on_connect_button_clicked(self, op, context: bpy.types.Context, id: int):
        pass

    @abstractmethod
    def on_recording_button_clicked(self, op, context: bpy.types.Context, id: int):
        pass


class MOCOPI_RECEIVER_OT_AvatarPanel(bpy.types.Operator):
    
    bl_idname = "mocopi_receiver_plugin.avatar_panel"
    bl_label = strings.get('bl_label_avatar_panel')
    bl_description = strings.get('bl_desc_avatar_panel')
    bl_options = {'INTERNAL', 'UNDO'}

    id: bpy.props.IntProperty() # type: ignore
    action: bpy.props.StringProperty() # type: ignore
    listener: IAvatarPanelListener = None

    def execute(self, context):

        if self.action == 'connect_button':
            self.listener.on_connect_button_clicked(self, context, self.id)
        elif self.action == 'recording_button':
            self.listener.on_recording_button_clicked(self, context, self.id)

        return {'FINISHED'} 
    

class MOCOPI_RECEIVER_PT_AvatarPanel(bpy.types.Panel):

    id: bpy.props.IntProperty(default=0) # type: ignore
    listener: IAvatarPanelListener = None
    
    # bl_idname = "MOCOPI_RECEIVER_PT_AvatarPanel"
    # bl_label = "Avatar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "mocopi"    

    def draw(self, context):

        MOCOPI_RECEIVER_OT_AvatarPanel.listener = MOCOPI_RECEIVER_PT_AvatarPanel.listener

        layout = self.layout
    
        # 更新のコールバック
        avatar = self.listener.on_drawed(self, context, self.id)
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(self.id)

        row = layout.row()
        row.label(text=strings.get('switch_mode') + ':')
        row.prop(prop, 'mode', expand=True)
        row.enabled = not avatar.running
            
        row = layout.row()
        row.label(text=strings.get('number_port') + ':')
        row.prop(prop, 'port', text='')
        row.enabled = not avatar.running

        row = layout.row()
        row.label(text=strings.get('connecting') if avatar.running else strings.get('unconnected'), icon='PLUGIN')
        op = row.operator(MOCOPI_RECEIVER_OT_AvatarPanel.bl_idname, text=strings.get('connect') if not avatar.running else strings.get('disconnect'))
        op.id = self.id
        op.action = 'connect_button'
        row.enabled = utils.is_valid(prop) and utils.is_armature(avatar.rig)

        # row = layout.row()
        # row.label(text=strings.get('model_type') + ':')
        # row.prop(prop, 'model_type', text='')

        # row = layout.row()
        # row.label(text='debug: ')
        # row.prop(prop, 'debug_id', text='')

        if prop.mode == 'v2':
            row = layout.row()
            row.label(text='')
            op = row.operator(MOCOPI_RECEIVER_OT_AvatarPanel.bl_idname, text=strings.get('start_recording') if not avatar.is_recording else strings.get('stop_recording'))
            op.id = self.id
            op.action = 'recording_button'
            row.enabled = avatar.running

        # ターゲット
        box = layout.box() 
        row = box.row()
        row.prop_search(prop, 'rig', search_data=bpy.data, search_property='objects', text=strings.get('character'))
        box.enabled = not avatar.running
        
        # ボーン
        if utils.is_valid(prop) and utils.is_armature(avatar.rig):
            box.prop_search(prop, 'root', search_data=avatar.rig.data, search_property='bones', text='Hip')
            box.prop_search(prop, 'torso_1', search_data=avatar.rig.data, search_property='bones', text='Torso1')
            box.prop_search(prop, 'torso_2', search_data=avatar.rig.data, search_property='bones', text='Torso2')
            box.prop_search(prop, 'torso_3', search_data=avatar.rig.data, search_property='bones', text='Torso3')
            box.prop_search(prop, 'torso_4', search_data=avatar.rig.data, search_property='bones', text='Torso4')
            box.prop_search(prop, 'torso_5', search_data=avatar.rig.data, search_property='bones', text='Torso5')
            box.prop_search(prop, 'torso_6', search_data=avatar.rig.data, search_property='bones', text='Torso6')
            box.prop_search(prop, 'torso_7', search_data=avatar.rig.data, search_property='bones', text='Torso7')
            box.prop_search(prop, 'neck_1', search_data=avatar.rig.data, search_property='bones', text='Neck1')
            box.prop_search(prop, 'neck_2', search_data=avatar.rig.data, search_property='bones', text='Neck2')
            box.prop_search(prop, 'head', search_data=avatar.rig.data, search_property='bones', text='Head')
            box.prop_search(prop, 'l_shoulder', search_data=avatar.rig.data, search_property='bones', text='L_Shoulder')
            box.prop_search(prop, 'l_up_arm', search_data=avatar.rig.data, search_property='bones', text='L_UpperArm')
            box.prop_search(prop, 'l_low_arm', search_data=avatar.rig.data, search_property='bones', text='L_LowerArm')
            box.prop_search(prop, 'l_hand', search_data=avatar.rig.data, search_property='bones', text='L_Hand')
            box.prop_search(prop, 'r_shoulder', search_data=avatar.rig.data, search_property='bones', text='R_Shoulder')
            box.prop_search(prop, 'r_up_arm', search_data=avatar.rig.data, search_property='bones', text='R_UpperArm')
            box.prop_search(prop, 'r_low_arm', search_data=avatar.rig.data, search_property='bones', text='R_LowerArm')
            box.prop_search(prop, 'r_hand', search_data=avatar.rig.data, search_property='bones', text='R_Hand')
            box.prop_search(prop, 'l_up_leg', search_data=avatar.rig.data, search_property='bones', text='L_UpperLeg')
            box.prop_search(prop, 'l_low_leg', search_data=avatar.rig.data, search_property='bones', text='L_LowerLeg')
            box.prop_search(prop, 'l_foot', search_data=avatar.rig.data, search_property='bones', text='L_Foot')
            box.prop_search(prop, 'l_toes', search_data=avatar.rig.data, search_property='bones', text='L_ToeBase')
            box.prop_search(prop, 'r_up_leg', search_data=avatar.rig.data, search_property='bones', text='R_UpperLeg')
            box.prop_search(prop, 'r_low_leg', search_data=avatar.rig.data, search_property='bones', text='R_LowerLeg')
            box.prop_search(prop, 'r_foot', search_data=avatar.rig.data, search_property='bones', text='R_Foot')
            box.prop_search(prop, 'r_toes', search_data=avatar.rig.data, search_property='bones', text='R_ToeBase')


class MOCOPI_RECEIVER_PT_Panel(bpy.types.Panel):

    bl_idname = "MOCOPI_RECEIVER_PT_Panel"
    bl_label = strings.get('mocopi')
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "mocopi"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=main.Main.image_collection["mocopi_icon"].icon_id)

    def draw(self, context):

        layout = self.layout
        layout.label(text=strings.get('ip_address') + ': ' + utils.get_ip_address())
