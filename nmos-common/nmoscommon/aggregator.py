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

from urlparse import urljoin
import requests
import json
import time

import gevent
import gevent.queue

from nmoscommon.logger import Logger
from nmoscommon.mdnsbridge import IppmDNSBridge

from nmoscommon import nmoscommonconfig
from nmoscommon import config as _config

AGGREGATOR_APIVERSION = _config.get('nodefacade', {}).get('NODE_REGVERSION', 'v1.1')
AGGREGATOR_APINAMESPACE = "x-nmos"
AGGREGATOR_APINAME = "registration"

REGISTRATION_MDNSTYPE = "nmos-registration"

# A map of translations for types of resource whose exposed registry
# name differs from the posted "type" attribute.
TYPE_TRANSLATIONS = {'flowsegment': 'flows'}

class NoAggregator(Exception):
    def __init__(self, mdns_updater = None):
        if mdns_updater is not None:
            mdns_updater.inc_P2P_enable_count()
        pass

class InvalidRequest(Exception):
    def __init__(self, status_code=400, mdns_updater = None):
        if mdns_updater is not None:
            mdns_updater.inc_P2P_enable_count()
        super(InvalidRequest, self).__init__("Invalid Request, code {}".format(status_code))
        self.status_code = status_code

class TooManyRetries(Exception):
    def __init__(self, mdns_updater = None):
        if mdns_updater is not None:
            mdns_updater.inc_P2P_enable_count()
        super(TooManyRetries, self).__init__("Too many retries.")

class Aggregator(object):
    """This class serves as a proxy for the distant aggregation service running elsewhere on the network.
    It will search out aggregators and locate them, falling back to other ones if the one it is connected to
    disappears, and resending data as needed."""
    def __init__(self, logger=None, mdns_updater=None):
        self.logger = Logger("aggregator_proxy", logger)
        self.mdnsbridge = IppmDNSBridge(logger=self.logger)
        self.aggregator = ""
        self.registration_order = ["device", "source", "flow", "sender", "receiver"]
        self._mdns_updater = mdns_updater
        # 'registered' is a local mirror of aggregated items. There are helper methods
        # for manipulating this below.
        self._registered = {
            'node': None,
            'registered': False,
            'entities': {
                'resource': {
                },
                'timeline': {
                    'flow': {}
                }
            }
        }
        self._running = True
        self._reg_queue = gevent.queue.Queue()
        self.heartbeat_thread = gevent.spawn(self._heartbeat)
        self.queue_thread = gevent.spawn(self._process_queue)

    # The heartbeat thread runs in the background every five seconds.
    # If when it runs the Node is believed to be registered it will perform a heartbeat
    def _heartbeat(self):
        self.logger.writeDebug("Starting heartbeat thread")
        while self._running:
            heartbeat_wait = 5
            if not self._registered["registered"]:
                self._process_reregister()
            elif self._registered["node"]:
                # Do heartbeat
                try:
                    self.logger.writeDebug("Sending heartbeat for Node {}".format(self._registered["node"]["data"]["id"]))
                    self._SEND("POST", "/health/nodes/" + self._registered["node"]["data"]["id"])
                except InvalidRequest as e:
                    if e.status_code == 404:
                        # Re-register
                        self.logger.writeWarning("404 error on heartbeat. Marking Node for re-registration")
                        self._registered["registered"] = False

                        if(self._mdns_updater is not None):
                            self._mdns_updater.inc_P2P_enable_count()
                    else:
                        # Client side error. Report this upwards via exception, but don't resend
                        self.logger.writeError("Unrecoverable error code {} received from Registration API on heartbeat".format(e.status_code))
                        self._running = False
                except:
                    # Re-register
                    self.logger.writeWarning("Unexpected error on heartbeat. Marking Node for re-registration")
                    self._registered["registered"] = False
            else:
                self._registered["registered"] = False
                if(self._mdns_updater is not None):
                    self._mdns_updater.inc_P2P_enable_count()
            while heartbeat_wait > 0 and self._running:
                gevent.sleep(1)
                heartbeat_wait -= 1
        self.logger.writeDebug("Stopping heartbeat thread")

    # Provided the Node is believed to be correctly registered, hand off a single request to the SEND method
    # On client error, clear the resource from the local mirror
    # On other error, mark Node as unregistered and trigger re-registration
    def _process_queue(self):
        self.logger.writeDebug("Starting HTTP queue processing thread")
        while self._running or (self._registered["registered"] and not self._reg_queue.empty()): # Checks queue not empty before quitting to make sure unregister node gets done
            if not self._registered["registered"] or self._reg_queue.empty():
                gevent.sleep(1)
            else:
                try:
                    queue_item = self._reg_queue.get()
                    namespace = queue_item["namespace"]
                    res_type = queue_item["res_type"]
                    res_key = queue_item["key"]
                    if queue_item["method"] == "POST":
                        if res_type == "node":
                            data = self._registered["node"]
                            try:
                                self.logger.writeInfo("Attempting registration for Node {}".format(self._registered["node"]["data"]["id"]))
                                self._SEND("POST", "/{}".format(namespace), data)
                                self._SEND("POST", "/health/nodes/" + self._registered["node"]["data"]["id"])
                                self._registered["registered"] = True
                                if self._mdns_updater is not None:
                                    self._mdns_updater.P2P_disable()

                            except Exception as ex:
                                self.logger.writeWarning("Error registering Node: {}".format(ex))

                        elif res_key in self._registered["entities"][namespace][res_type]:
                            data = self._registered["entities"][namespace][res_type][res_key]
                            try:
                                self._SEND("POST", "/{}".format(namespace), data)
                            except InvalidRequest as e:
                                self.logger.writeWarning("Error registering {} {}: {}".format(res_type, res_key, e))
                                self.logger.writeWarning("Request data: {}".format(self._registered["entities"][namespace][res_type][res_key]))
                                del self._registered["entities"][namespace][res_type][res_key]

                    elif queue_item["method"] == "DELETE":
                        translated_type = TYPE_TRANSLATIONS.get(res_type, res_type + 's')
                        try:
                            self._SEND("DELETE", "/{}/{}/{}".format(namespace, translated_type, res_key))
                        except InvalidRequest as e:
                            self.logger.writeWarning("Error deleting resource {} {}: {}".format(translated_type, res_key, e))
                    else:
                        self.logger.writeWarning("Method {} not supported for Registration API interactions".format(queue_item["method"]))
                except Exception as e:
                    self._registered["registered"] = False
                    if(self._mdns_updater is not None):
                        self._mdns_updater.P2P_disable()
        self.logger.writeDebug("Stopping HTTP queue processing thread")

    # Queue a request to be processed. Handles all requests except initial Node POST which is done in _process_reregister
    def _queue_request(self, method, namespace, res_type, key):
        self._reg_queue.put({"method": method, "namespace": namespace, "res_type": res_type, "key": key})

    # Register 'resource' type data including the Node
    # NB: Node registration is managed by heartbeat thread so may take up to 5 seconds!
    def register(self, res_type, key, **kwargs):
        self.register_into("resource", res_type, key, **kwargs)

    # Unregister 'resource' type data including the Node
    def unregister(self, res_type, key):
        self.unregister_from("resource", res_type, key)

    # General register method for 'resource' and 'timeline' types
    def register_into(self, namespace, res_type, key, **kwargs):
        data = kwargs
        send_obj = {"type": res_type, "data": data}
        if 'id' not in send_obj["data"]:
            self.logger.writeWarning("No 'id' present in data, using key='{}': {}".format(key, data))
            send_obj["data"]["id"] = key

        if namespace == "resource" and res_type == "node":
            # Handle special Node type
            self._registered["node"] = send_obj
        else:
            self._add_mirror_keys(namespace, res_type)
            self._registered["entities"][namespace][res_type][key] = send_obj
        self._queue_request("POST", namespace, res_type, key)

    # General unregister method for 'resource' and 'timeline' types
    def unregister_from(self, namespace, res_type, key):
        if namespace == "resource" and res_type == "node":
            # Handle special Node type
            self._registered["node"] = None
        elif res_type in self._registered["entities"][namespace]:
            self._add_mirror_keys(namespace, res_type)
            if key in self._registered["entities"][namespace][res_type]:
                del self._registered["entities"][namespace][res_type][key]
        self._queue_request("DELETE", namespace, res_type, key)

    # Deal with missing keys in local mirror
    def _add_mirror_keys(self, namespace, res_type):
        if namespace not in self._registered["entities"]:
            self._registered["entities"][namespace] = {}
        if res_type not in self._registered["entities"][namespace]:
            self._registered["entities"][namespace][res_type] = {}

    # Re-register just the Node, and queue requests in order for other resources
    def _process_reregister(self):
        if self._registered.get("node", None) is None:
            self.logger.writeDebug("No node registered, re-register returning")
            return

        try:
            self.logger.writeDebug("Clearing old Node from API prior to re-registration")
            self._SEND("DELETE", "/resource/nodes/" + self._registered["node"]["data"]["id"])
        except InvalidRequest as e:
            # 404 etc is ok
            self.logger.writeInfo("Invalid request when deleting Node prior to registration: {}".format(e))
        except Exception as ex:
            # Server error is bad, no point continuing
            self.logger.writeError("Aborting Node re-register! {}".format(ex))
            return

        self._registered["registered"] = False
        if(self._mdns_updater is not None):
            self._mdns_updater.inc_P2P_enable_count()

        # Drain the queue
        while not self._reg_queue.empty():
            try:
                self._reg_queue.get(block=False)
            except gevent.queue.Queue.Empty:
                break

        try:
            # Register the node, and immediately heartbeat if successful to avoid race with garbage collect.
            self.logger.writeInfo("Attempting re-registration for Node {}".format(self._registered["node"]["data"]["id"]))
            self._SEND("POST", "/resource", self._registered["node"])
            self._SEND("POST", "/health/nodes/" + self._registered["node"]["data"]["id"])
            self._registered["registered"] = True
            if self._mdns_updater is not None:
                self._mdns_updater.P2P_disable()
        except Exception as e:
            self.logger.writeWarning("Error re-registering Node: {}".format(e))
            return

        # Re-register items that must be ordered
        # Re-register things we have in the local cache.
        # "namespace" is e.g. "resource", or "timeline".
        # "entities" are the things associated under that namespace.
        for res_type in self.registration_order:
            for namespace, entities in self._registered["entities"].items():
                if res_type in entities:
                    self.logger.writeInfo("Ordered re-registration for type: '{}' in namespace '{}'".format(res_type, namespace))
                    for key in entities[res_type]:
                        self._queue_request("POST", namespace, res_type, key)

        # Re-register everything else
        # Re-register things we have in the local cache.
        # "namespace" is e.g. "resource", or "timeline".
        # "entities" are the things associated under that namespace.
        for namespace, entities in self._registered["entities"].items():
            for res_type in entities:
                if res_type not in self.registration_order:
                    self.logger.writeInfo("Unordered re-registration for type: '{}' in namespace '{}'".format(res_type, namespace))
                    for key in entities[res_type]:
                        self._queue_request("POST", namespace, res_type, key)

    # Stop the Aggregator object running
    def stop(self):
        self.logger.writeDebug("Stopping aggregator proxy")
        self._running = False
        self.heartbeat_thread.join()
        self.queue_thread.join()

    # Handle sending all requests to the Registration API, and searching for a new 'aggregator' if one fails
    def _SEND(self, method, url, data=None):
        if self.aggregator == "":
            self.aggregator = self.mdnsbridge.getHref(REGISTRATION_MDNSTYPE)

        if data is not None:
            data = json.dumps(data)

        url = AGGREGATOR_APINAMESPACE + "/" + AGGREGATOR_APINAME + "/" + AGGREGATOR_APIVERSION + url
        for i in range(0, 3):
            if self.aggregator == "":
                self.logger.writeWarning("No aggregator available on the network or mdnsbridge unavailable")
                raise NoAggregator(self._mdns_updater)

            self.logger.writeDebug("{} {}".format(method, urljoin(self.aggregator, url)))

            # We give a long(ish) timeout below, as the async request may succeed after the timeout period
            # has expired, causing the node to be registered twice (potentially at different aggregators).
            # Whilst this isn't a problem in practice, it may cause excessive churn in websocket traffic
            # to web clients - so, sacrifice a little timeliness for things working as designed the
            # majority of the time...
            try:
                if nmoscommonconfig.config.get('prefer_ipv6',False) == False:
                    R = requests.request(method, urljoin(self.aggregator, url), data=data, timeout=1.0)
                else:
                    R = requests.request(method, urljoin(self.aggregator, url), data=data, timeout=1.0, proxies={'http':''})
                if R is None:
                    # Try another aggregator
                    self.logger.writeWarning("No response from aggregator {}".format(self.aggregator))

                elif R.status_code in [200, 201]:
                    if R.headers.get("content-type", "text/plain").startswith("application/json"):
                        return R.json()
                    else:
                        return R.content

                elif R.status_code == 204:
                    return

                elif (R.status_code/100) == 4:
                    self.logger.writeWarning("{} response from aggregator: {} {}".format(R.status_code, method, urljoin(self.aggregator, url)))
                    raise InvalidRequest(R.status_code, self._mdns_updater)

                else:
                    self.logger.writeWarning("Unexpected status from aggregator {}: {}, {}".format(self.aggregator, R.status_code, R.content))

            except requests.exceptions.RequestException as ex:
                # Log a warning, then let another aggregator be chosen
                self.logger.writeWarning("{} from aggregator {}".format(ex, self.aggregator))

            # This aggregator is non-functional
            self.aggregator = self.mdnsbridge.getHref(REGISTRATION_MDNSTYPE)
            self.logger.writeInfo("Updated aggregator to {} (try {})".format(self.aggregator, i))

        raise TooManyRetries(self._mdns_updater)

if __name__ == "__main__":
    from uuid import uuid4

    agg = Aggregator()
    ID = str(uuid4())

    agg.register("node", ID, id=ID, label="A Test Service", href="http://127.0.0.1:12345/", services=[], caps={}, version="0:0", hostname="apiTest")
    try:
        while True:
            time.sleep(1)
    except:
        agg.unregister("node", ID)
        agg.stop()

class MDNSUpdater:
    def __init__(self, mdns_engine, mdns_type, mdns_name , mappings, port, logger, p2p_enable=False, p2p_cut_in_count=5, txt_recs=None):
        self.mdns = mdns_engine
        self.mdns_type = mdns_type
        self.mdns_name = mdns_name
        self.mappings = mappings
        self.port = port
        self.service_versions = {}
        self.txt_rec_base = {}
        if txt_recs:
            self.txt_rec_base = txt_recs
        self.logger = logger
        self.p2p_enable = p2p_enable
        self.p2p_enable_count = 0
        self.p2p_cut_in_count = p2p_cut_in_count

        for mapValue in self.mappings.itervalues():
            self.service_versions[mapValue] = 0

        self.mdns.register(self.mdns_name, self.mdns_type, self.port, self.txt_rec_base)

    def _p2p_txt_recs(self):
        txt_recs = self.txt_rec_base.copy()
        txt_recs.update(self.service_versions)
        return txt_recs

    def update_mdns(self, type, action):
        if self.p2p_enable:
            if (action == "register") or (action == "update") or (action == "unregister"):
                self.logger.writeDebug("mDNS action: {} {}".format(action, type))
                self._increment_service_version(type)
                self.mdns.update(self.mdns_name, self.mdns_type, self._p2p_txt_recs())

    def _increment_service_version(self, type):
        self.service_versions[self.mappings[type]] = self.service_versions[self.mappings[type]]+1
        if self.service_versions[self.mappings[type]] > 255:
            self.service_versions[self.mappings[type]] = 0

    #Counts up a number of times, and then enables P2P
    def inc_P2P_enable_count(self):
        if not self.p2p_enable:
            self.p2p_enable_count += 1
            if self.p2p_enable_count >= self.p2p_cut_in_count:
                self.P2P_enable()

    def _reset_P2P_enable_count(self):
        self.p2p_enable_count = 0

    def P2P_enable(self):
        if not self.p2p_enable:
            self.logger.writeInfo("Enabling P2P Discovery");
            self.p2p_enable = True
            self.mdns.update(self.mdns_name, self.mdns_type, self._p2p_txt_recs())

    def P2P_disable(self):
        if self.p2p_enable:
            self.logger.writeInfo("Disabling P2P Discovery");
            self.p2p_enable = False
            self._reset_P2P_enable_count()
            self.mdns.update(self.mdns_name, self.mdns_type, self.txt_rec_base)
        else:
            self._reset_P2P_enable_count()
