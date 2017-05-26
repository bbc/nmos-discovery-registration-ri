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

from gevent import monkey; monkey.patch_all()

import json
import signal
import time
import gevent
import os

from nmoscommon.httpserver import HttpServer
from nmoscommon.logger import Logger
from nmoscommon.mdns import MDNSEngine
from nmosquery.api import QueryServiceAPI
from nmoscommon.utils import getLocalIP

reg = {'host': 'localhost', 'port': 4001}
WS_PORT = 8870
DNS_SD_PORT = 80


class QueryService:

    def __init__(self, logger=None):
        self.running = False
        self.logger = Logger("regquery")
        self.logger.writeDebug('Running QueryService')
        self.config = {"priority": 0}
        self._load_config()
        self.mdns = MDNSEngine()
        self.httpServer = HttpServer(QueryServiceAPI, WS_PORT, '0.0.0.0', api_args=[self.logger])

    def start(self):
        if self.running:
            gevent.signal(signal.SIGINT,  self.sig_handler)
            gevent.signal(signal.SIGTERM, self.sig_handler)

        self.running = True
        self.mdns.start()

        HOST = getLocalIP()

        self.logger.writeDebug('Running web socket server on %i' % WS_PORT)

        self.httpServer.start()

        while not self.httpServer.started.is_set():
            self.logger.writeDebug('Waiting for httpserver to start...')
            self.httpServer.started.wait()

        if self.httpServer.failed is not None:
            raise self.httpServer.failed

        self.logger.writeDebug("Running on port: {}".format(self.httpServer.port))

        priority = self.config["priority"]
        if not str(priority).isdigit() or priority < 100:
            priority = 0

        self.mdns.register('query_' + str(HOST), '_nmos-query._tcp', DNS_SD_PORT,
                           {"pri": priority,
                            "api_ver": "v1.0,v1.1,v1.2",
                            "api_proto": "http"})

    def run(self):
        self.running = True
        self.start()
        while self.running:
            time.sleep(1)
        self._cleanup()

    def _cleanup(self):
        self.mdns.stop()
        self.mdns.close()
        self.httpServer.stop()

    def sig_handler(self):
        self.stop()

    def stop(self):
        self.running = False

    def _load_config(self):
        try:
            config_file = "/etc/nmos-query/config.json"
            if os.path.isfile(config_file):
                f = open(config_file, 'r')
                extra_config = json.loads(f.read())
                self.config.update(extra_config)
        except Exception as e:
            self.logger.writeDebug("Exception loading config: {}".format(e))
