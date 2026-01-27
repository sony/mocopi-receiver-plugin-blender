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
import bpy.utils.previews
import os
from . import views
from . import models
from . import properties
from . import utils
from . import strings

class Main(properties.IMocopiAvatarPropertyListener, views.IAvatarPanelListener):

    classes = [
        properties.MocopiAvatarProperty,
        properties.MocopiAvatarProperty_1,
        properties.MocopiAvatarProperty_2,
        properties.MocopiAvatarProperty_3,
        properties.MocopiProperty,
        views.MOCOPI_RECEIVER_PT_Panel,
        views.MOCOPI_RECEIVER_OT_AvatarPanel,
        type(
            'MOCOPI_RECEIVER_AvatarPanel_1',
            (views.MOCOPI_RECEIVER_PT_AvatarPanel,),
            {
                'bl_idname': 'MOCOPI_RECEIVER_PT_AvatarPanel_1',
                'bl_label': f"{strings.get('mocopi_receiver')} [1]",
                'id': 1,
            }
        ), 
        type(
            'MOCOPI_RECEIVER_AvatarPanel_2',
            (views.MOCOPI_RECEIVER_PT_AvatarPanel,),
            {
                'bl_idname': 'MOCOPI_RECEIVER_PT_AvatarPanel_2',
                'bl_label': f"{strings.get('mocopi_receiver')} [2]",
                'bl_options': {'DEFAULT_CLOSED'},
                'id': 2,
            }
        ), 
        type(
            'MOCOPI_RECEIVER_AvatarPanel_3',
            (views.MOCOPI_RECEIVER_PT_AvatarPanel,),
            {
                'bl_idname': 'MOCOPI_RECEIVER_PT_AvatarPanel_3',
                'bl_label': f"{strings.get('mocopi_receiver')} [3]",
                'bl_options': {'DEFAULT_CLOSED'},
                'id': 3,
            }
        ),
    ]
    image_collection = None

    avatars: list[models.Avatar] = []

    def __init__(self):
        pass

    # Public

    def register(self):

        # 多言語対応
        bpy.app.translations.register(__name__, strings.locals)

        # 画像リソース
        Main.image_collection = bpy.utils.previews.new()
        Main.image_collection.load("mocopi_icon", f"{os.path.dirname(__file__)}/assets/mocopiSDK_Color.png", 'IMAGE')

        # リスナー登録
        properties.MocopiAvatarProperty.listener = self
        views.MOCOPI_RECEIVER_PT_Panel.listener = self
        views.MOCOPI_RECEIVER_PT_AvatarPanel.listener = self

        # パネルとオペレータ
        for c in Main.classes:
            bpy.utils.register_class(c)

        # プロパティ
        properties.MocopiProperty.register()

        # アバター
        self.avatars.append(models.Avatar(1, Main.classes[5]))
        self.avatars.append(models.Avatar(2, Main.classes[6]))
        self.avatars.append(models.Avatar(3, Main.classes[7]))

        # 定期処理
        bpy.app.timers.register(self.__update, persistent=False)

    def unregister(self):

        # # 定期処理
        # bpy.app.timers.unregister(self.__update)

        # プロパティ
        properties.MocopiProperty.unregister()

        # パネルとオペレータ
        for c in Main.classes:
            bpy.utils.unregister_class(c)
        
        # 画像リソース
        bpy.utils.previews.remove(Main.image_collection)

        # 多言語対応
        bpy.app.translations.unregister(__name__)

    # IMocopiAvatarPropertyListener

    def on_rig_updated(self, context: bpy.types.Context, id: int, rig: bpy.types.Object):

        avatar = self.__find_avatar(id)
        if not avatar:
            return 
        
        # オートリターゲット
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)
        prop.auto_retarget(rig)
        avatar.retarget(rig, prop)

    def on_bone_updated(self, context: bpy.types.Context, id: int, rig: str):
        
        avatar = self.__find_avatar(id)
        if not avatar:
            return
        
        # リターゲット
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)
        avatar.retarget(avatar.rig, prop)

    def on_debug_id_updated(self, context: bpy.types.Context, id: int, debug_id: int):

        avatar = self.__find_avatar(id)
        if not avatar:
            return
        
        # デバッグID更新
        avatar.debug_id = debug_id
        print(f"debug_id: {avatar.debug_id}")

    # IAvatarPanelListener

    def on_drawed(self, panel: views.MOCOPI_RECEIVER_PT_AvatarPanel, context: bpy.types.Context, id: int) -> models.Avatar:

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)
        if not utils.is_valid(prop):
            return None
        
        avatar = self.__find_avatar(id)
        if not avatar:
            return None
        
        if avatar.running and not utils.is_armature(avatar.rig):
            avatar.stop()

        return avatar

    def on_connect_button_clicked(self, op: views.MOCOPI_RECEIVER_OT_AvatarPanel, context: bpy.types.Context, id: int):

        avatar = self.__find_avatar(id)
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)
        if not avatar.running:

            # mocopi接続
            if prop.mode == 'v1':

                if not utils.is_valid(prop) or not utils.is_armature(avatar.rig):
                    op.report({'WARNING'}, strings.get('msg_target_is_not_armature'))
                    return
                
                avatar.retarget(avatar.rig, prop)
                avatar.run()

                if not avatar.running:
                    op.report({'WARNING'}, strings.get('msg_confirm_port'))
                    return

                # 記録開始
                self.__start_keyframe() # キーフレーム再生

            elif prop.mode == 'v2':

                avatar.run()

                if not avatar.running:
                    op.report({'WARNING'}, strings.get('msg_confirm_port'))
                    return

        else: 

            # 記録終了
            self.__stop_keyframe() # キーフレーム停止

            # mocopi切断
            avatar.stop()

    def on_recording_button_clicked(self, op, context: bpy.types.Context, id: int):

        avatar = self.__find_avatar(id)
        if not avatar:
            return
        
        if avatar.is_recording:
            avatar.stop_recording()
            if bpy.context.screen.is_animation_playing:
                self.__stop_keyframe() # キーフレーム停止

                avatar.stop()
                avatar.run()
        else:
            avatar.start_recording()
            self.__start_keyframe() # キーフレーム再生

    # Private

    def __update(self):

        if bpy.context.selected_objects:
            self.__stop_keyframe() # キーフレーム停止
            return 0
        
        for avatar in self.avatars:
            avatar.update()
            if avatar.running and not utils.is_armature(avatar.rig):
                avatar.stop()
                self.__stop_keyframe() # キーフレーム停止

        # if any(avatar.running for avatar in self.avatars) and not bpy.context.screen.is_animation_playing:
        #     self.__start_keyframe() # キーフレーム再生
        return 0

    def __start_keyframe(self):
        if not bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

    def __stop_keyframe(self):
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

    def __find_avatar(self, id: int) -> models.Avatar:
        for avatar in self.avatars:
            if avatar.id == id:
                return avatar
        return None