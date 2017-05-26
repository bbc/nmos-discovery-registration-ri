# Copyright 2017 British Broadcasting Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json


class GrainEvent(object):
    def __init__(self):
        self.grains = []
        self.source_id = '0000-0000-0000-0000'
        self.flow_id = '0000-0000-0000-0000'
        self.ts = '0:0'
        self.topic = ''

    def addGrainFromObj(self, pre_obj=None, post_obj=None):
        if pre_obj is None:
            pre_obj = {}
        if post_obj is None:
            post_obj = {}
        uid = pre_obj.get('id', '')
        if uid == '':
            uid = post_obj.get('id', '')
        grain = {
            "path": uid,
            "pre": pre_obj,
            "post": post_obj
        }

        self.grains.append(grain)

    def clearGrains(self):
        del self.grains[:]

    def obj(self):
        retVal = {
            "grain_type": "event",
            "source_id": self.source_id,  # Query service instance ID should be persistent for a given system
            "flow_id": self.flow_id,      # Subscription ID
            "origin_timestamp": self.ts,
            "sync_timestamp": self.ts,
            "creation_timestamp": self.ts,
            "rate": {"numerator": 0, "denominator": 1},
            "duration": {"numerator": 0, "denominator": 1},
            "grain": {
                "type": "urn:x-nmos:format:data.event",
                "topic": "/{}/".format(self.topic.strip('/')),
                "data": self.grains
            }
        }

        return retVal

    def str(self):
        return json.dumps(self.obj())
