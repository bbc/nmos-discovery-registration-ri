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

import time, threading, copy

from nmoscommon.logger import Logger
from nmoscommon import ptptime
from copy import deepcopy
from api import NODE_APIVERSIONS
from api import NODE_REGVERSION
from api import NODE_APINAMESPACE
from api import NODE_APINAME
import re
import copy
import json

from nmoscommon import config as _config

HEARTBEAT_TIMEOUT = 12 # Seconds
CLEANUP_INTERVAL = 5 # Seconds

#TODO: Enumerate return codes better?

RES_SUCCESS = 0
RES_EXISTS = 1
RES_NOEXISTS = 2
RES_UNAUTHORISED = 3
RES_UNSUPPORTED = 4
RES_OTHERERROR = 5


class FacadeRegistryCleaner(threading.Thread):
    def __init__(self, registry):
        self.stopping = False
        self.registry = registry
        super(FacadeRegistryCleaner, self).__init__()
        self.daemon = True

    def run(self):
        loopcount = 0
        while not self.stopping:
            time.sleep(1)
            loopcount += 1
            if loopcount >= CLEANUP_INTERVAL:
                self.registry.cleanup_services()
                loopcount = 0

    def stop(self):
        self.stopping = True
        self.join()


def api_version_less_than(a, b):
    ver_a = a[1:].split(".")
    ver_b = b[1:].split(".")
    return ver_a[0] < ver_b[0] or (ver_a[0] == ver_b[0] and ver_a[1] < ver_b[1])

def legalise_resource(res, rtype, api_version):
    RESOURCE_CORE_V1_1 = [ "id",
                           "version",
                           "label",
                           "description",
                           "tags" ]
    # v1.0 begins
    legalkeys = {
        ("node", "v1.0") : [
            "id",
            "version",
            "label",
            "href",
            "hostname",
            "caps",
            "services",
            ],
        ("device", "v1.0") : [
            "id",
            "version",
            "label",
            "type",
            "node_id",
            "senders",
            "receivers"
            ],
        ("source", "v1.0") : [
            "id",
            "label",
            "description",
            "format",
            "caps",
            "tags",
            "parents",
            "version",
            "device_id",
            ],
        ("flow", "v1.0") : [
            "id",
            "version",
            "label",
            "description",
            "tags",
            "format",
            "tags",
            "source_id",
            "parents",
            ],
        ("sender", "v1.0") : [
            "id",
            "version",
            "label",
            "description",
            "flow_id",
            "transport",
            "tags",
            "device_id",
            "manifest_href",
            ],
        ("receiver", "v1.0") : [
            "id",
            "version",
            "label",
            "description",
            "format",
            "caps",
            "tags",
            "device_id",
            "transport",
            "subscription"
            ]
    }
    # v1.0 ends

    # v1.1 begins
    legalkeys[("node", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                    legalkeys[("node", "v1.0")] +
                                    ["api", "clocks"] )
    legalkeys[("device", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                      legalkeys[("device", "v1.0")] +
                                      ["controls"] )
    legalkeys[("source", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                      legalkeys[("source", "v1.0")] +
                                      ["clock_name", "grain_rate"] +
                                      ["channels"] )
    legalkeys[("flow", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                    legalkeys[("flow", "v1.0")] +
                                    ["device_id", "grain_rate", "media_type"] +
                                    ["sample_rate", "bit_depth"] +
                                    ["DID_SDID"] +
                                    ["frame_width", "frame_height",
                                     "interlace_mode", "colorspace",
                                     "components", "transfer_characteristic"] )
    legalkeys[("sender", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                      legalkeys[("sender", "v1.0")] )
    legalkeys[("receiver", "v1.1")] = ( RESOURCE_CORE_V1_1 +
                                        legalkeys[("receiver", "v1.0")] )
    # v1.1 ends

    # v1.2 begins
    legalkeys[("node", "v1.2")] = ( legalkeys[("node", "v1.1")] +
                                    ["interfaces"] )
    legalkeys[("device", "v1.2")] = ( legalkeys[("device", "v1.1")] )
    legalkeys[("source", "v1.2")] = ( legalkeys[("source", "v1.1")] )
    legalkeys[("flow", "v1.2")] = ( legalkeys[("flow", "v1.1")] )
    legalkeys[("sender", "v1.2")] = ( legalkeys[("sender", "v1.1")] +
                                      ["interface_bindings"] )
    legalkeys[("receiver", "v1.2")] = ( legalkeys[("receiver", "v1.1")] +
                                        ["interface_bindings"] )
    # v1.2 ends

    if (rtype, api_version) not in legalkeys:
        return res

    retval = dict()
    for key in legalkeys[(rtype, api_version)]:
        if key in res:
            retval[key] = res[key]
    return retval

class FacadeRegistry(object):
    def __init__(self, resources, aggregator, mdns_updater, node_id, node_data, logger=None):

        # `node_data` must be correctly structured
        self.permitted_resources = resources
        self.services = {}
        self.aggregator = aggregator
        self.mdns_updater = mdns_updater
        self.node_id = node_id
        assert("interfaces" in node_data) # Check data conforms to latest supported API version
        self.node_data = node_data
        self.logger = Logger("facade_registry", logger)

    def modify_node(self, **kwargs):
        for key in kwargs.keys():
            if key in self.node_data:
                self.node_data[key] = kwargs[key]
        self.update_node()

    def update_node(self):
        self.node_data["services"] = []
        for service_name in self.services:
            href = None
            if self.services[service_name]["href"]:
                if self.services[service_name]["proxy_path"]:
                    href = "http://{}/{}".format(self.node_data["host"],self.services[service_name]["proxy_path"])
            self.node_data["services"].append({"href": href, "type": self.services[service_name]["type"]})
        self.node_data["version"] = str(ptptime.ptp_detail()[0]) + ":" + str(ptptime.ptp_detail()[1])
        try:
            self.aggregator.register("node", self.node_id, **legalise_resource(self.node_data, "node", NODE_REGVERSION))
        except Exception as e:
            self.logger.writeError("Exception re-registering node: {}".format(e))

    def register_service(self, name, srv_type, pid, href=None, proxy_path=None):
        if name in self.services:
            return RES_EXISTS

        self.services[name] = {
            "heartbeat": time.time(),
            "resource": {},                     # Registered resources live under here
            "timeline": {"flowsegment": {}},    # Registered "timeline" items live under here
            "pid": pid,
            "href": href,
            "proxy_path": proxy_path,
            "type": srv_type
        }

        for resource_name in self.permitted_resources:
            self.services[name]["resource"][resource_name] = {}

        self.update_node()
        return RES_SUCCESS

    def update_service(self, name, pid, href=None, proxy_path=None):
        if not name in self.services:
            return RES_NOEXISTS
        if self.services[name]["pid"] != pid:
            return RES_UNAUTHORISED
        self.services[name]["heartbeat"] = time.time()
        self.services[name]["href"] = href
        self.services[name]["proxy_path"] = proxy_path
        self.update_node()
        return RES_SUCCESS

    def unregister_service(self, name, pid):
        if not name in self.services:
            return RES_NOEXISTS
        if self.services[name]["pid"] != pid:
            return RES_UNAUTHORISED
        for namespace in ["resource", "timeline"]:
            for type in self.services[name][namespace].keys():
                for key in self.services[name][namespace][type].keys():
                    self._unregister(name, namespace, pid, type, key)
        self.services.pop(name, None)
        self.update_node()
        return RES_SUCCESS

    def heartbeat_service(self, name, pid):
        if not name in self.services:
            return RES_NOEXISTS
        if self.services[name]["pid"] != pid:
            return RES_UNAUTHORISED
        self.services[name]["heartbeat"] = time.time()
        return RES_SUCCESS

    def cleanup_services(self):
        timed_out = time.time() - HEARTBEAT_TIMEOUT
        for name in self.services.keys():
            if self.services[name]["heartbeat"] < timed_out:
                self.unregister_service(name, self.services[name]["pid"])

    def register_resource(self, service_name, pid, type, key, value):
        if not type in self.permitted_resources:
            return RES_UNSUPPORTED
        return self._register(service_name, "resource", pid, type, key, value)

    def register_to_timeline(self, service_name, pid, type, key, value):
        return self._register(service_name, "timeline", pid, type, key, value)

    def _register(self, service_name, namespace, pid, type, key, value):
        if "max_api_version" not in value:
            self.logger.writeWarning("Service {}: Registration without valid api version specified".format(service_name))
            value["max_api_version"] = "v1.0"
        elif api_version_less_than(value["max_api_version"], NODE_REGVERSION):
            self.logger.writeWarning("Trying to register resource with api version too low: \"%s\" : %s", key, json.dumps(value))
        if not service_name in self.services:
            return RES_NOEXISTS
        if not self.services[service_name]["pid"] == pid:
            return RES_UNAUTHORISED
        if key == "00000000-0000-0000-0000-000000000000":
            return RES_OTHERERROR

        # Add a node_id to those resources which need one
        if type == 'device':
            value['node_id'] = self.node_id

        self.services[service_name][namespace][type][key] = value

        # Don't pass non-registration exceptions to clients
        try:
            self._update_mdns(type)
        except Exception as e:
            self.logger.writeError("Exception registering with mDNS: {}".format(e))

        try:
            self.aggregator.register_into(namespace, type, key, **legalise_resource(value, type, NODE_REGVERSION))
            self.logger.writeDebug("registering {} {}".format(type, key))
        except Exception as e:
            self.logger.writeError("Exception registering {}: {}".format(namespace, e))
            return RES_OTHERERROR
        return RES_SUCCESS

    def update_resource(self, service_name, pid, type, key, value):
        return self.register_resource(service_name, pid, type, key, value)

    def find_service(self, type, key):
        for service_name in self.services.keys():
            if key in self.services[service_name]["resource"][type]:
                return service_name
        return None

    def update_timeline(self, service_name, pid, type, key, value):
        return self._register(service_name, "timeline", pid, type, key, value)

    def unregister_resource(self, service_name, pid, type, key):
        if not type in self.permitted_resources:
            return RES_UNSUPPORTED
        return self._unregister(service_name, "resource", pid, type, key)

    def unregister_from_timeline(self, service_name, pid, type, key):
        return self._unregister(service_name, "timeline", pid, type, key)

    def _unregister(self, service_name, namespace, pid, type, key):
        if not service_name in self.services:
            return RES_NOEXISTS
        if not self.services[service_name]["pid"] == pid:
            return RES_UNAUTHORISED
        if key == "00000000-0000-0000-0000-000000000000":
            return RES_OTHERERROR
        self.services[service_name][namespace][type].pop(key, None)
        # Don't pass non-registration exceptions to clients
        try:
            self.aggregator.unregister_from(namespace, type, key)
        except Exception as e:
            self.logger.writeError("Exception unregistering {}: {}".format(namespace, e))
            return RES_OTHERERROR
        try:
            self._update_mdns(type)
        except Exception as e:
            extype, exmsg = e
            self.logger.writeError("Exception unregistering from mDNS: {}".format(e))
            if extype != -65548: # Name conflict
                return RES_OTHERERROR
        return RES_SUCCESS

    def list_services(self, api_version="v1.0"):
        return self.services.keys()

    def get_service_href(self, name, api_version="v1.0"):
        if not name in self.services:
            return RES_NOEXISTS
        href = self.services[name]["href"]
        if self.services[name]["proxy_path"]:
            href += "/" + self.services[name]["proxy_path"]
        return href

    def get_service_type(self, name, api_version="v1.0"):
        if not name in self.services:
            return RES_NOEXISTS
        return self.services[name]["type"]

    def list_resource(self, type, api_version="v1.0"):
        if not type in self.permitted_resources:
            return RES_UNSUPPORTED
        response = {}
        for name in self.services:
            response = (dict(response.items() + [ (k, legalise_resource(x, type, api_version))
                                                  for (k,x) in self.services[name]["resource"][type].items()
                                                  if ((api_version == "v1.0") or
                                                      ("max_api_version" in x and
                                                       not api_version_less_than(x["max_api_version"], api_version))) ]))
        return response

    def _update_mdns(self, type):
        items = self.list_resource(type)
        if not isinstance(items, dict):
            return
        if len(items) == 1:
            try:
                self.mdns_updater.update_mdns(type, "register")
            except Exception:
                self.mdns_updater.update_mdns(type, "update")
        elif len(items) == 0:
            self.mdns_updater.update_mdns(type, "unregister")
        else:
            self.mdns_updater.update_mdns(type, "update")

    def list_self(self, api_version="v1.0"):
        return legalise_resource(self.node_data, "node", api_version)

    def update_ptp(self):
        do_update = False
        for clk in self.node_data['clocks']:
            if "ref_type" in clk and clk["ref_type"] == "ptp":
                old_clk = copy.copy(clk)
                clk['traceable'] = False
                clk['gmid'] = '00-00-00-00-00-00-00-00'
                clk['locked'] = False
                if clk != old_clk:
                    do_update = True
        if do_update:
            self.update_node()

if __name__ == "__main__":
    import uuid
    registry = FacadeRegistry()
    print "Registering service and flow"
    registry.register_service("pipelinemanager", 100, "http://127.0.0.1:12345")
    test_key = str(uuid.uuid4())
    registry.register_resource("pipelinemanager", "flow", test_key, {"label": "test"})
    registry.cleanup_services()
    print "Find Service:", registry.find_service("flow", test_key)
    print "Self:", registry.list_self()
    print "Flows:", registry.list_resource("flow")
    print "Sources:", registry.list_resource("source")
    print "Sleeping for", HEARTBEAT_TIMEOUT+1 ,"seconds"
    time.sleep(HEARTBEAT_TIMEOUT+1)
    registry.cleanup_services()
    #registry.unregister_service("pipelinemanager", 100)
    print "Self:", registry.list_self()
    print "Flows:", registry.list_resource("flow")
    print "Soures:", registry.list_resource("source")
