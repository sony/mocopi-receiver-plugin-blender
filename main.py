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
import traceback
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
        self._timer_callback = self.__update

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
        self.avatars.clear()
        self.avatars.append(models.Avatar(1, Main.classes[5]))
        self.avatars.append(models.Avatar(2, Main.classes[6]))
        self.avatars.append(models.Avatar(3, Main.classes[7]))

        # 定期処理
        self.__ensure_timer_registered()

    def unregister(self):

        # 定期処理
        if bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.unregister(self._timer_callback)

        # mocopi切断
        for avatar in self.avatars:
            avatar.stop()
        self.avatars.clear()

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
        resolved_rig = utils.resolve_armature(rig)
        prop.auto_retarget(resolved_rig)
        avatar.retarget(resolved_rig, prop)

    def on_bone_updated(self, context: bpy.types.Context, id: int, rig: str):
        
        avatar = self.__find_avatar(id)
        if not avatar:
            return
        
        # リターゲット
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)
        if avatar.running and utils.is_valid(prop) and prop.mode == 'v2':
            return
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

        # .blend再ロード後の参照切れ対策として毎描画で参照を再同期する
        resolved_rig = utils.resolve_armature(prop.rig)
        if avatar.running and prop.mode == 'v2':
            return avatar

        # 実行中は一時的な参照不整合で None 上書きしない
        if utils.is_armature(resolved_rig):
            avatar.retarget(resolved_rig, prop)
        elif not avatar.running:
            avatar.retarget(None, prop)

        return avatar

    def on_connect_button_clicked(self, op: views.MOCOPI_RECEIVER_OT_AvatarPanel, context: bpy.types.Context, id: int):

        # 接続前に更新タイマーを再保証（再ロード後や例外後の停止対策）
        self.__ensure_timer_registered()

        avatar = self.__find_avatar(id)
        if not avatar:
            return

        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)

        if not utils.is_valid(prop):
            op.report({'WARNING'}, 'mocopi property is not initialized.')
            return

        # 接続開始時にプロパティ上のrigをアーマチュアとして再同期
        resolved_rig = utils.resolve_armature(prop.rig)
        if resolved_rig != prop.rig and utils.is_armature(resolved_rig):
            prop.rig = resolved_rig

        avatar.retarget(resolved_rig, prop)

        # どのモードでも接続開始時にターゲットアーマチュアは必須
        # Abort if the target armature is not valid
        if not avatar.running and not utils.is_armature(avatar.rig):
            op.report({'WARNING'}, strings.get('msg_target_is_not_armature'))
            return

        if not avatar.running:

            if hasattr(bpy.app, 'online_access') and not bpy.app.online_access:
                op.report({'WARNING'}, 'Blender Online Access is disabled. Enable it for mocopi UDP receive.')
                return

            # mocopi接続
            avatar.run()

            # avatar.run() reports failure (port already in use, invalid rig) by leaving running False
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

        # prop: used to access the settings and rig associated with this avatar
        prop: properties.MocopiAvatarProperty = bpy.context.scene.mocopi_property.get(id)

        if avatar.is_recording:
            avatar.stop_recording()
            screen = bpy.context.screen

            # capture playback state first; __stop_keyframe() clears is_animation_playing
            was_playing = bool(screen and screen.is_animation_playing)

            # ensure keyframe stopped only when animation is actively playing
            if was_playing:
                self.__stop_keyframe() # キーフレーム停止

            # for v2, rebuild hidden skeleton/retarget constraints
            if was_playing and utils.is_valid(prop) and prop.mode == 'v2':
                avatar.stop()
                avatar.run()

        elif avatar.is_counting_down:
            avatar.cancel_recording_countdown()
        else:
            avatar.begin_recording_countdown(3.0)

    # Private

    def __update(self):
        try:
            context = bpy.context
            if not context or not context.scene:
                return 0.1

            scene = context.scene
            mocopi_prop = getattr(scene, 'mocopi_property', None)

            for avatar in self.avatars:
                if mocopi_prop:
                    prop = mocopi_prop.get(avatar.id)
                    if utils.is_valid(prop):
                        resolved_rig = utils.resolve_armature(prop.rig)
                        if avatar.running and prop.mode == 'v2':
                            avatar.update()
                            if avatar.just_started_recording:
                                self.__start_keyframe() # start keyframe recording
                                avatar.just_started_recording = False
                            continue

                        # 実行中は有効な参照を None で潰さない
                        if utils.is_armature(resolved_rig) and resolved_rig != avatar.rig:
                            avatar.retarget(resolved_rig, prop)
                        elif (not avatar.running) and resolved_rig != avatar.rig:
                            avatar.retarget(resolved_rig, prop)

                avatar.update()

                if avatar.just_started_recording:
                    self.__start_keyframe()
                    avatar.just_started_recording = False

            # if any(avatar.running for avatar in self.avatars) and not bpy.context.screen.is_animation_playing:
            #     self.__start_keyframe() # キーフレーム再生
            return 0.01
        except Exception:
            # タイマー例外でコールバックが消えるのを避ける
            traceback.print_exc()
            return 0.1

    def __ensure_timer_registered(self):
        if not bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.register(self._timer_callback, persistent=True)

    def __start_keyframe(self):
        screen = bpy.context.screen
        if screen and not screen.is_animation_playing:
            bpy.ops.screen.animation_play()

    def __stop_keyframe(self):
        screen = bpy.context.screen
        if screen and screen.is_animation_playing:
            bpy.ops.screen.animation_play()

    def __find_avatar(self, id: int) -> models.Avatar:
        for avatar in self.avatars:
            if avatar.id == id:
                return avatar
        return None