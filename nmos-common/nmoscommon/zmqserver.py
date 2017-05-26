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

import zmq
import threading
import json


class ZmqServer(threading.Thread):
    """ServerTask"""
    def __init__(self, callback, numWorkers=5, host="*", port=5570):
        threading.Thread.__init__(self)
        self.callback = callback
        self.port = port
        self.host = host
        self.numWorkers = numWorkers
        self.workers = []

    def run(self):
        """Sets up an internal router that routes requests to one
        of many worker threads that handle the calls out to the routes"""
        self.context = zmq.Context()
        self.frontend = self.context.socket(zmq.ROUTER)
        self.frontend.bind('tcp://' + self.host + ":" + str(self.port))

        self.backend = self.context.socket(zmq.DEALER)
        self.backend.bind('inproc://backend')

        """Spin up a bunch of workers to handle reqests"""
        for i in range(self.numWorkers):
            worker = ServerWorker(self.callback, self.context)
            worker.start()
            self.workers.append(worker)

        try:
            """This method blocks here until termination"""
            zmq.proxy(self.frontend, self.backend)
        except zmq.ZMQError:
            """Handle cleanly the exception thrown when the context is
            torn down when we finish"""
            pass

    def stop(self):
        for worker in self.workers:
            worker.amRunning = False
            while not worker.finished:
                pass
        self.context.destroy()


class ServerWorker(threading.Thread):
    """Serveral instances of these run in different threads to handle
    zmq requests as they come in. This method only wants to be sent JSON,
    please don't send it anything else..."""
    def __init__(self, callback, context):
        threading.Thread.__init__(self)
        self.poller = zmq.Poller()
        self.context = context
        self.amRunning = True
        self.finished = False
        self.callback = callback

    def run(self):
        """Blocking method that runs until amRunning is set false"""
        # Connect to the socket
        worker = self.context.socket(zmq.DEALER)
        self.poller.register(worker, zmq.POLLIN)
        worker.connect('inproc://backend')
        while self.amRunning:
            # Loop round checking for messages until the end
            socks = dict(self.poller.poll(timeout=100))
            if worker in socks:
                # Received a message, do something with it
                ident, msg = worker.recv_multipart()
                try:
                    msg = json.loads(msg)
                except ValueError:
                    response = [400]
                    worker.send_multipart([ident], json.dumps(response))
                finally:
                    response = self.callback(msg)
                    worker.send_multipart([ident, json.dumps(response)])
        self.finished = True
        return
