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

import requests
import random
import os
import json

from nmoscommonconfig import config as _config

from nmoscommon.logger import Logger

class IppmDNSBridge(object):
    def __init__(self, logger=None):
        self.logger = Logger("mdnsbridge", logger)
        self.services = {}
        self.config = {"priority": 0}
        self.config.update(_config)

    def _checkLocalQueryServiceExists(self):
        url = "http://127.0.0.1/x-nmos/query/v1.0/";
        try:
            # Request to localhost:18870/ - if it succeeds, the service exists AND is running AND is accessible
            r = requests.get(url, timeout=0.5)
            if r is not None and r.status_code == 200:
                # If any results, put them in self.services
                return url

        except Exception as e:
            self.logger.writeWarning("No local query service running {}".format(e))
        return ""

    def getHref(self, srv_type, priority=None):
        if priority == None:
            priority = self.config["priority"]

        if self.logger != None:
            self.logger.writeDebug("IppmDNSBridge priority = {}".format(priority))

        # Check if type is in services. If not add it
        if srv_type not in self.services:
            self.services[srv_type] = []

        # Check if there are any of that type of service, if not do a request
        no_results = True
        for service in self.services[srv_type]:
            if priority >= 100:
                if service["priority"] == priority:
                    no_results = False
            elif service["priority"] < 100:
                no_results = False
        if no_results:
            self._updateServices(srv_type)

        # Re-check if there are any and return "" if not.
        current_priority = 99
        valid_services = []
        for service in self.services[srv_type]:
            if priority >= 100:
                if service["priority"] == priority:
                    return self._createHref(service["address"], service["port"])
            else:
                if service["priority"] < current_priority:
                    current_priority = service["priority"]
                    valid_services = []
                if service["priority"] == current_priority:
                    valid_services.append(service)
        if len(valid_services) == 0:
            self.logger.writeWarning("No services found: {}".format(srv_type))
            if srv_type == "nmos-query":
                return self._checkLocalQueryServiceExists()
            return ""

        # Randomise selection. Delete entry from the services list and return it
        random.seed()
        index = random.randint(0, len(valid_services)-1)
        service = valid_services[index]
        href = self._createHref(service["address"], service["port"])
        self.services[srv_type].remove(service)
        return href

    def _createHref(self, address, port):
        formatted_address = address
        if ":" in formatted_address:
            formatted_address = "[" + formatted_address + "]"
        return "http://" + formatted_address + ":" + str(port)

    def _updateServices(self, srv_type):
        req_url = "http://127.0.0.1/x-nmos-opensourceprivatenamespace/mdnsbridge/v1.0/" + srv_type + "/";
        try:
            # Request to localhost/x-nmos-opensourceprivatenamespace/mdnsbridge/v1.0/<type>/
            r = requests.get(req_url, timeout=0.5, proxies={'http': ''})
            if r is not None and r.status_code == 200:
                # If any results, put them in self.services
                self.services[srv_type] = r.json()["representation"]
        except Exception as e:
            self.logger.writeWarning("Exception updating services: {}".format(e))

if __name__ == "__main__":
    bridge = IppmDNSBridge()
    print bridge.getHref("nmos-registration")
