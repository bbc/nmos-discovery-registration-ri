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

import os
import traceback
from ipc import Proxy
import gevent
from threading import Lock
from nmoscommon.logger import Logger
from copy import deepcopy

FAC_SUCCESS = 0
FAC_EXISTS = 1
FAC_UNREGISTERED = 2
FAC_UNAUTHORISED = 3
FAC_UNSUPPORTED = 4
FAC_OTHERERROR = 5

class Facade(object):
    """This class serves as a proxy for the Facade running on the same machine if it exists. If no facade exists
    on this machine then it will do nothing, but calls will still function without throwing any exceptions."""
    def __init__(self, srv_type, address="ipc:///tmp/ips-nodefacade",logger=None):
        self.logger          = Logger("facade_proxy", logger)
        self.ipc             = None
        self.srv_registered  = False # Flag whether service is registered
        self.reregister      = False # Flag whether resources are correctly registered
        self.address         = address
        self.srv_type        = srv_type.lower()
        self.srv_type_urn    = "urn:x-nmos-opensourceprivatenamespace:service:" + self.srv_type
        self.pid             = os.getpid()
        self.resources       = {}
        self.timeline        = {}
        self.href            = None
        self.proxy_path      = None
        self.lock            = Lock() # Protect access to IPC socket

    def setup_ipc(self):
        with self.lock:
            try:
                self.ipc = Proxy(self.address)
            except:
                self.ipc = None

    def register_service(self, href, proxy_path):
        self.logger.writeInfo("Register service")
        self.href = href
        self.proxy_path = proxy_path
        if not self.ipc:
            self.setup_ipc()
        if not self.ipc:
            return
        try:
            with self.lock:
                s = self.ipc.srv_register(self.srv_type, self.srv_type_urn, self.pid, href, proxy_path)
                if s == FAC_SUCCESS:
                    self.srv_registered = True
                else:
                    self.logger.writeInfo("Service registration failed: {}".format(self.debug_message(s)))
        except Exception as e:
            self.ipc = None

    def unregister_service(self):
        if not self.ipc:
            self.setup_ipc()
        if not self.ipc:
            return
        try:
            with self.lock:
                self.ipc.srv_unregister(self.srv_type, self.pid)
                self.srv_registered = False
        except Exception as e:
            self.ipc = None

    def heartbeat_service(self):
        if not self.ipc:
            self.setup_ipc()
        if not self.ipc:
            return
        try:
            with self.lock:
                s = self.ipc.srv_heartbeat(self.srv_type, self.pid)
                if s != FAC_SUCCESS:
                    self.srv_registered = False
                    self.logger.writeInfo("Heartbeat failed: {}".format(self.debug_message(s)))
                else:
                    self.srv_registered = True
            if not self.srv_registered or self.reregister:
                # Handle reconnection if facade disappears
                self.logger.writeInfo("Reregistering all services")
                self.reregister_all()
        except Exception as e:
            self.ipc = None

    # ONLY call this directly from within heartbeat_service!
    # To cause a re-registration on failure, set self.reregister!
    def reregister_all(self):
        self.unregister_service()
        if self.srv_registered:
            return
        self.register_service(self.href, self.proxy_path)
        if not self.srv_registered:
            return

        # TODO: the following blocks are so similar...

        # re-register resources
        for type in self.resources:
            for key in self.resources[type]:
                try:
                    with self.lock:
                        resource = self.resources[type][key]
                        # Hide some implementation details for receivers
                        if type == "receiver":
                            resource = deepcopy(self.resources[type][key])
                            if "pipel_id" in self.resources[type][key]:
                                resource.pop('pipel_id')
                            if "pipeline_id" in self.resources[type][key]:
                                resource.pop('pipeline_id')
                        self.ipc.res_register(self.srv_type, self.pid, type, key, resource)
                except Exception as e:
                    self.ipc = None
                    gevent.sleep(0)
                    return

        # re-register timeline items
        for type in self.timeline:
            for key in self.timeline[type]:
                try:
                    with self.lock:
                        self.ipc.timeline_register(self.srv_type, self.pid, type, key, self.timeline[type][key])
                except Exception as e:
                    self.ipc = None
                    gevent.sleep(0)
                    return

        self.reregister = False

    def _call_ipc_method(self, method, *args, **kwargs):
        if not self.srv_registered:
            # Don't attempt if not registered - will just hit many timeouts
            self.reregister = True
            return
        if not self.ipc:
            self.setup_ipc()
        if not self.ipc:
            self.reregister = True
            return
        try:
            with self.lock:
                return self.ipc.invoke_named(method, self.srv_type, self.pid, *args, **kwargs)
        except Exception as e:
            self.ipc = None
            self.reregister = True

    def addResource(self, type, key, value):
        if type not in self.resources:
            self.resources[type] = {}
        self.resources[type][key] = value
        self._call_ipc_method("res_register", type, key, value)

    def updateResource(self, type, key, value):
        if type not in self.resources:
            self.resources[type] = {}
        self.resources[type][key] = value
        self._call_ipc_method("res_update", type, key, value)

    def delResource(self, type, key):
        if type in self.resources:
            # Hack until adoption of flow instances (Ensure transports for flow are deleted)
            if type == "flow" and "transport" in self.resources:
                for transport in self.resources["transport"].keys():
                    if key == self.resources["transport"][transport]["flow-id"]:
                        del self.resources["transport"][transport]
            if key in self.resources[type]:
                del self.resources[type][key]
        self._call_ipc_method("res_unregister", type, key)

    def addTimeline(self, type, key, value):
        if type not in self.timeline:
            self.timeline[type] = {}
        self.timeline[type][key] = value
        self._call_ipc_method("timeline_register", type, key, value)

    def updateTimeline(self, type, key, value):
        if type not in self.timeline:
            self.timeline[type] = {}
        self.timeline[type][key] = value
        self._call_ipc_method("timeline_update", type, key, value)

    def delTimeline(self, type, key):
        if type in self.timeline:
            if key in self.timeline[type]:
                del self.timeline[type][key]
        self._call_ipc_method("timeline_unregister", type, key)

    def get_node_self(self, api_version="v1.1"):
        return self._call_ipc_method("self_get", api_version)

    def debug_message(self, code):
        msg =  {FAC_SUCCESS:"Success!",
                FAC_EXISTS:"Service already exists",
                FAC_UNREGISTERED:"Service isn't yet registered",
                FAC_UNAUTHORISED:"Unauthorised",
                FAC_UNSUPPORTED:"Unsupported",
                FAC_OTHERERROR:"Other error"} [code]
        return msg
