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

from nmoscommon.mdns import MDNSEngine
from nmoscommon.utils import getLocalIP
from nmosregistration.aggregation import AggregatorAPI
from nmoscommon.httpserver import HttpServer
from nmoscommon.logger import Logger
import signal
import time

import os
import json

import gevent
from gevent import monkey
monkey.patch_all()

HOST = getLocalIP()
SERVICE_PORT = 8235
DNS_SD_PORT = 80
REGISTRY_PORT = 4001

class RegistryAggregatorService(object):
    def __init__(self, logger=None, interactive=False):
        self.config      = {"priority": 0}
        self._load_config()
        self.running     = False
        self.httpServer  = None
        self.interactive = interactive
        self.mdns        = MDNSEngine()
        self.logger      = Logger("aggregation", logger)

    def _load_config(self):
        try:
            config_file = "/etc/nmos-registration/config.json"
            if os.path.isfile(config_file):
                f = open(config_file, 'r')
                extra_config = json.loads(f.read())
                self.config.update(extra_config)
        except Exception as e:
            print "Exception loading config: {}".format(e)

    def start(self):
        if self.running:
            gevent.signal(signal.SIGINT,  self.sig_handler)
            gevent.signal(signal.SIGTERM, self.sig_handler)

        self.mdns.start()

        self.httpServer = HttpServer(AggregatorAPI, SERVICE_PORT, '0.0.0.0', api_args=[self.logger, self.config])
        self.httpServer.start()
        while not self.httpServer.started.is_set():
            print 'Waiting for httpserver to start...'
            self.httpServer.started.wait()

        if self.httpServer.failed is not None:
            raise self.httpServer.failed

        print "Running on port: {}".format(self.httpServer.port)

        priority = self.config["priority"]
        if not str(priority).isdigit() or priority < 100:
            priority = 0

        self.mdns.register('registration_' + str(HOST),
                           '_nmos-registration._tcp', DNS_SD_PORT,
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
        print "Stopped main()"

    def stop(self):
        self.running = False

    def sig_handler(self):
        print 'Pressed ctrl+c'
        self.stop()
