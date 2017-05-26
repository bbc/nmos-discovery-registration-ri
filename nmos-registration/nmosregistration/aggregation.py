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

from nmoscommon.utils import getLocalIP
from nmoscommon.webapi import WebAPI, route
from etcd_backend import EtcdInterface
from nmosregistration.garbage import GarbageCollect

from nmosregistration.v1_0 import routes as v1_0
from nmosregistration.v1_1 import routes as v1_1
from nmosregistration.v1_2 import routes as v1_2

HOST = getLocalIP()
SERVICE_PORT = 8235

AGGREGATOR_APINAMESPACE = "x-nmos"
AGGREGATOR_APINAME = "registration"

class AggregatorAPI(WebAPI):

    def __init__(self, logger, config, registry=EtcdInterface()):
        super(AggregatorAPI, self).__init__()
        self._config = config

        garbage_collect_interval = int(self._config.get("garbage_collect_interval", 10))
        self._garbage_collector = GarbageCollect(identifier=HOST, registry=registry, interval=garbage_collect_interval)

        self._v1_0_api = v1_0.Routes(logger=logger, registry=registry)
        self.add_routes(self._v1_0_api, basepath="/x-nmos/registration/v1.0")

        self._v1_1_api = v1_1.Routes(logger=logger, registry=registry)
        self.add_routes(self._v1_1_api, basepath="/x-nmos/registration/v1.1")

        self._v1_2_api = v1_2.Routes(logger=logger, registry=registry)
        self.add_routes(self._v1_2_api, basepath="/x-nmos/registration/v1.2")

    @route('/')
    def __root(self):
        return (200, [AGGREGATOR_APINAMESPACE+"/"])

    @route('/'+AGGREGATOR_APINAMESPACE+'/')
    def __namespaceroot(self):
        return (200, [AGGREGATOR_APINAME+"/"])

    @route('/'+AGGREGATOR_APINAMESPACE+'/'+AGGREGATOR_APINAME+'/')
    def __nameroot(self):
        return (200, ["v1.0/", "v1.1/", "v1.2/"])
