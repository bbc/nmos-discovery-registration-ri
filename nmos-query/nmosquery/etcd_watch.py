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

from gevent import monkey
monkey.patch_all()

import gevent
import gevent.queue
import requests
import time
import socket

from nmoscommon.logger import Logger

def _get_etcd_index(request, logger):
    """
    Return the etcd "index" from the x-etcd-index header of the request.
    If the header is not present, return 0.
    If the header is present, but cannot be read as an `int', return 0.
    """
    index = 0
    try:
        index = int(request.headers.get("x-etcd-index", 0))
    except Exception as ex:
        logger.writeWarning("Unexpected exception getting x-etcd-index: {}".format(ex))
        index = 0
    return index

class EtcdEventQueue(object):
    """
    Attempt to overcome the "missed etcd event" issue, which can be caused when
    processing of a return from a http long-poll takes too long, and an event is
    missed in etcd.

    This uses etcd's "waitIndex" functionality, which has the caveat that only
    the last 1000 events are stored. So, whilst this scheme should not miss events
    for fast updates, the case where 1000 updates occur within the space of a
    single event being processed will still be missed. This is unlikely, but still
    possible, so a "sentinel" message with action=index_skip will be sent to
    the output queue when this happens.

    To use this, the `queue' member of EtcdEventQueue is iterable:

    q = EtcdEventQueue()
    for message in q.queue:
        # process

    This uses http://www.gevent.org/gevent.queue.html as an underlying data
    structure, so can be consumed from multiple greenlets if necessary.
    """

    def __init__(self, host, port, logger=None):
        self.queue = gevent.queue.Queue()
        self._base_url = "http://{}:{}/v2/keys/resource/".format(host, port)
        self._long_poll_url = self._base_url + "?recursive=true&wait=true"
        self._greenlet = gevent.spawn(self._wait_event, 0)
        self._alive = True
        self._logger = Logger("etcd_watch", logger)

    def _get_index(self, current_index):
        index = current_index
        try:
            response = requests.get(self._base_url, proxies={'http': ''}, timeout=1)
            if response is not None:
                if response.status_code == 200:
                    index = _get_etcd_index(response, self._logger)
                    self._logger.writeDebug("waitIndex now = {}".format(index))

                    # Always want to know if the index we were waiting on was greater
                    # than current index, as this indicates something that needs further
                    # investigation...
                    if index < current_index:
                        self._logger.writeWarning("Index decreased! {} -> {}".format(current_index, index))

                elif response.status_code in [400, 404]:
                    # '/resource' not found in etcd yet, back off for a second and set waitIndex to value of the x-etcd-index header
                    index = int(response.headers.get('x-etcd-index', 0))
                    self._logger.writeInfo("{} not found, wait... waitIndex={}".format(self._base_url, index))
                    gevent.sleep(1)

            else:
                # response was None...
                self._logger.writeWarning("Could not GET {} after timeout; waitIndex now=0".format(self._base_url))
                index = 0

        except Exception as ex:
            # Getting the new index failed, so reset to 0.
            self._logger.writeWarning("Reset waitIndex to 0, error: {}".format(ex))
            index = 0

        return index

    def _wait_event(self, since):
        current_index = since

        while self._alive:
            req = None
            try:
                # Make the long-poll request to etcd using the current
                # "waitIndex".  A timeout is used as situations have been
                # observed where the etcd modification index decreases (caused
                # by network partition or by a node having it's data reset?),
                # and the query service is not restarted, hence the code below
                # is left waiting for a much higher modification index than it
                # should.  To mitigate this simply, when a timeout occurs,
                # assume that the modified index is "wrong", and forcibly try
                # to fetch the next index. This may "miss" updates, which is of
                # limited consequence. An enhancement (and therefore
                # complication...) could use the fact that the timeout is
                # small, and set waitIndex to the x-etcd-index result minus
                # some heuristically determined number of updates, to try and
                # catch the "back-in-time" updates stored in etcd's log, but
                # this feels brittle and overcomplicated for something that
                # could be solved by a browser refresh/handling of the "skip"
                # event to request a full set of resources.

                # https://github.com/coreos/etcd/blob/master/Documentation/api.md#waiting-for-a-change
                next_index_param = "&waitIndex={}".format(current_index + 1)
                req = requests.get(self._long_poll_url + next_index_param, proxies={'http': ''}, timeout=20)

            except socket.timeout:
                # Get a new wait index to watch from by querying /resource
                self._logger.writeDebug("Timeout waiting on long-poll. Refreshing waitIndex...")
                current_index = self._get_index(current_index)
                continue

            except Exception as ex:
                self._logger.writeWarning("Could not contact etcd: {}".format(ex))
                gevent.sleep(5)
                continue

            if req is not None:
                # Decode payload, which should be json...
                try:
                    json = req.json()

                except Exception:
                    self._logger.writeError("Error decoding payload: {}".format(req.text))
                    continue

                if req.status_code == 200:
                    # Return from request was OK, so put the payload on the queue.
                    # NOTE: we use the "modifiedIndex" of the _node_ we receive, NOT the header.
                    # This follows the etcd docs linked above.
                    self.queue.put(json)
                    current_index = json.get('node', {}).get('modifiedIndex', current_index)

                else:
                    # Error codes documented here:
                    #  https://github.com/coreos/etcd/blob/master/Documentation/errorcode.md
                    self._logger.writeInfo("error: http:{}, etcd:{}".format(req.status_code, json.get('errorCode', 0)))
                    if json.get('errorCode', 0) == 401:
                        # Index has been cleared. This may cause missed events, so send an (invented) sentinel message to queue.
                        new_index = self._get_index(current_index)
                        self._logger.writeWarning("etcd history not available; skipping {} -> {}".format(current_index, new_index))
                        self.queue.put({'action': 'index_skip', 'from': current_index, 'to': new_index})
                        current_index = new_index

    def stop(self):
        self._logger.writeInfo("Stopping service")
        print "stopping"
        self._alive = False
        self._greenlet.kill(timeout=5)
        self.queue.put(StopIteration)


if __name__ == '__main__':

    q = EtcdEventQueue("localhost", 4001)
    exist = set()

    for event in q.queue:

        gevent.sleep(0.3)
        action = event.get('action')

        if action == "set":
            value = event.get('node', {}).get('value', {})
            exist.add(value)
        elif action == "delete":
            value = event.get('prevNode', {}).get('value', {})
            if value in exist:
                exist.remove(value)
        else:
            print event

        print len(exist), q.queue.qsize(), time.time()
