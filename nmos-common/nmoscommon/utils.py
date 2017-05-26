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

import uuid
import json
import os
import netifaces

from logger import Logger

def get_node_id():
    logger = Logger("utils", None)
    node_id_path = "/var/nmos-node/facade.json"
    node_id = str(uuid.uuid1())
    try:
        if os.path.exists(node_id_path):
            f = open(node_id_path, "r")
            node_id = json.loads(f.read())["node_id"]
            f.close()
        else:
            f = open(node_id_path, "w")
            f.write(json.dumps({"node_id": node_id}))
            f.close()
    except Exception as e:
        logger.writeWarning("Unable to read or write node ID. Using dynamically generated ID")
        logger.writeWarning(str(e))
    return node_id

def getLocalIP():
    interfaces= netifaces.interfaces()
    for interface in interfaces:
        if (interface is not None) & (interface != 'lo'):
            return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
