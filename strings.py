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

locals = {
    "en_US": {
        ("*", "mocopi"): "mocopi",
        ("*", "add"): "Add",
        ("*", "avatar"): "Avatar",
        ("*", "remove"): "Remove",
        ("*", "connect"): "Connect",
        ("*", "disconnect"): "Disconnect",
        ("*", "skeleton"): "Skeleton",
        ("*", "number_port"): "port",
        ("*", "connecting"): "Connecting",
        ("*", "unconnected"): "Unconnected",
        ("*", "start_recording"): "Start Recording",
        ("*", "stop_recording"): "Stop Recording",
        ("*", "recording_starting_in"): "Recording in {0}s...",
        ("*", "animation"): "Animation",
        ("*", "clear"): "Clear",
        ("*", "start"): "Start",
        ("*", "stop"): "Stop",
        ("*", "options"): "Options",
        ("*", "open"): "Open",
        ("*", "close"): "Close",
        ("*", "target"): "Target",
        ("*", "character"): "Character",
        ("*", "reboot"): "Reboot",
        ("*", "switch_mode"): "Mode",
        ("*", "reset"): "Reset",

        ("*", "mocopi_rig"): "mocopi Rig",
        ("*", "mocopi_receiver"): "mocopi Receiver",
        ("*", "add_mocopi_receiver"): "Add mocopi Receiver",
        ("*", "reboot_mocopi_receiver"): "Reboot Receiver",
        ("*", "ip_address"): "IP Address",
        ("*", "model_type"): "Model Type",
        ("*", "record_with_keyframe"): "Record with Keyframe",
        ("*", "regenerate_rig"): "Regenerate Rig",
        ("*", "bake_animation"): "Bake Animation",
        ("*", "legacy_mode"): "Legacy",
        ("*", "generic_mode"): "Generic",
        ("*", "model_type"): "Model Type",
        ("*", "standard"): "Standard",
        ("*", "mixamo"): "Mixamo",

        ("*", "bl_label_panel"): "Panel",
        ("*", "bl_desc_panel"): "Panel (mocopi receiver plugin).",

        ("*", "bl_label_avatar_panel"): "Avatar Panel",
        ("*", "bl_desc_avatar_panel"): "Avatar Panel (mocopi receiver plugin).",

        ("*", "msg_confirm_port"): "You cannot use the same port number. Please confirm the port number.",
        ("*", "msg_missing_receiver"): "Please recreate the mocopi receiver panel.",
        ("*", "msg_target_is_not_armature"): "Target is not armature.",
    },
    "ja_JP": {
        ("*", "mocopi"): "mocopi",
        ("*", "add"): "追加",
        ("*", "avatar"): "アバター",
        ("*", "remove"): "削除",
        ("*", "connect"): "接続開始",
        ("*", "disconnect"): "接続終了",
        ("*", "start_recording"): "記録開始",
        ("*", "stop_recording"): "記録終了",
        ("*", "recording_starting_in"): "あと{0}秒で記録開始...",
        ("*", "skeleton"): "スケルトン",
        ("*", "number_port"): "ポート番号",
        ("*", "unconnected"): "未接続",
        ("*", "connecting"): "接続中",
        ("*", "animation"): "アニメーション",
        ("*", "clear"): "クリア", 
        ("*", "start"): "開始",
        ("*", "stop"): "停止",     
        ("*", "options"): "オプション",
        ("*", "open"): "開く",
        ("*", "close"): "閉じる",
        ("*", "target"): "ターゲット",
        ("*", "character"): "キャラクター",
        ("*", "reboot"): "再起動",
        ("*", "switch_mode"): "モード切替",
        ("*", "reset"): "リセット",

        ("*", "mocopi_rig"): "mocopiリグ",
        ("*", "mocopi_receiver"): "mocopiレシーバー",
        ("*", "add_mocopi_receiver"): "mocopiレシーバーを追加",
        ("*", "reboot_mocopi_receiver"): "レシーバーを再起動",
        ("*", "ip_address"): "IPアドレス",
        ("*", "model_type"): "モデルタイプ",
        ("*", "record_with_keyframe"): "キーフレーム記録",
        ("*", "regenerate_rig"): "リグを再生成",
        ("*", "bake_animation"): "アニメーションをベイク",
        ("*", "legacy_mode"): "従来モード",
        ("*", "generic_mode"): "汎用モード",
        ("*", "model_type"): "モデルタイプ",
        ("*", "standard"): "標準",
        ("*", "mixamo"): "mixamo",

        ("*", "bl_label_panel"): "パネル",
        ("*", "bl_desc_panel"): "mocopiレシーバーのパネル。",

        ("*", "bl_label_avatar_panel"): "mocopiレシーバーパネル",
        ("*", "bl_desc_avatar_panel"): "mocopiレシーバーのレシーバーパネル。",
        
        ("*", "msg_confirm_port"): "同じポート番号は使用できません。ポート番号を確認してください。",
        ("*", "msg_missing_receiver"): "レシーバーを作り直してください。",
        ("*", "msg_target_is_not_armature"): "Targetがアーマチュアではありません。",
    }
}

def get(id: str) -> str:
    lang = bpy.app.translations.locale
    if lang not in locals:
        lang = "en_US"
    return bpy.app.translations.pgettext(locals[lang].get(("*", id), id))