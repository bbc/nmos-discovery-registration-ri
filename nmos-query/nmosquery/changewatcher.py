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

import gevent

import nmosquery.etcd_watch as etcd_watch

class ChangeWatcher(gevent.Greenlet):
    def __init__(self, host, port, handler, logger):
        gevent.Greenlet.__init__(self)
        self.host = host
        self.port = port
        self.handler = handler
        self.logger = logger
        self.events = None

    def _run(self):
        retries = 0
        secs = [0, 1, 3, 10]  # incrementing retry sleep
        self.events = etcd_watch.EtcdEventQueue(self.host, self.port, self.logger)
        self.running = True
        while self.running:
            try:
                # Wait for queued events, and process each. This "blocks" until
                # the event queue is drained (see etcd_watch.EtcdEventQueue.stop)
                for event in self.events.queue:
                    self.handler._process_response(event)

            except Exception as e:
                retries += 1
                if (retries > 3):
                    retries = 3
                    # At this point, the registry has probably died, so disconnect any client websockets
                    # TODO: really?
                    self.logger.writeError('Disconnecting all subscribed WebSocket clients')
                    self.handler.query_sockets.del_all_socks()
                self.logger.writeError('comms err: {}'.format(e))
                gevent.sleep(secs[retries])

    def stop(self):
        self.running = False
        if self.events is not None:
            self.events.stop()
        self.kill(timeout=5)
