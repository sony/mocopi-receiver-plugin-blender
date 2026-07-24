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
from . import main

bl_info = {
    "name": "mocopi Receiver",
    "author": "Sony Corporation",
    "description": "mocopiと連携してアニメーションを記録します。",
    "blender": (4, 2, 5),
    "version": (2, 3, 0),
    "location": "3Dビューポート > メニュー",
    "warning": "",
    "support": "COMMUNITY", # COMMUNITY, TESTING
    "doc_url": "",
    "tracker_url": "",
    "category": "Animation",
}
    
main = main.Main()

def register():
    main.register()      

def unregister():
    main.unregister()

if __name__ == "__main__":
    register()