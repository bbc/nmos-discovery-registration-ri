#!/usr/bin/python

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

import signal, time
from nmoscommon.httpserver import HttpServer
from proxylisting import ProxyListingAPI

HOST = "127.0.0.1"
PORT = 12344

class ProxyListingService:
    def __init__(self):
        self.running = False

    def start(self):
        if self.running:
            signal.signal(signal.SIGINT, self.sig_handler)

        self.http_server = HttpServer(ProxyListingAPI, PORT, HOST)
        self.http_server.start()
        while not self.http_server.started.is_set():
            print "Waiting for httpserver to start..."
            self.http_server.started.wait()

        if self.http_server.failed is not None:
            raise self.http_server.failed

        print "Running on port: {}".format(self.http_server.port)

    def run(self):
        self.running = True
        self.start()
        while self.running:
            time.sleep(1)
        self.stop()

    def stop(self):
        if self.running:
            self.running = False
        else:
            self.http_server.stop()
            print "Stopped main()"

    def sig_handler(self, sig, frame):
        print "Pressed ctrl+c"
        self.stop()


if __name__ == "__main__":

    service = ProxyListingService()
    service.start()

    try:
        while True:
            time.sleep(1)
    except:
        service.stop()
