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
import json
import requests
import websocket
import itertools

from nmoscommon.logger import Logger

from nmoscommon import nmoscommonconfig
from nmoscommon import config as _config

QUERY_APIVERSION = _config.get('nodefacade', {}).get('NODE_REGVERSION', 'v1.1')
QUERY_APINAMESPACE = "x-nmos"
QUERY_APINAME = "query"
QUERY_MDNSTYPE = "nmos-query"

class BadSubscriptionError(Exception):
    pass


class QueryNotFoundError(Exception):
    pass


class QueryService(object):

    def __init__(self, mdns_bridge, logger=None, apiversion=QUERY_APIVERSION,  priority=None):
        self.mdns_bridge = mdns_bridge
        self._query_url = self.mdns_bridge.getHref(QUERY_MDNSTYPE, priority)
        iter = 0
        #TODO FIXME: Remove once IPv6 work complete and Python can use link local v6 correctly
        while "fe80:" in self._query_url:
            self._query_url = self.mdns_bridge.getHref(QUERY_MDNSTYPE, priority)
            iter += 1
            if iter > 20:
                break
        self.logger = Logger("nmoscommon.query", logger)
        self.apiversion = apiversion
        self.priority = priority

    def _get_query(self, url):
        backoff = [0.3, 0.7, 1.0]
        for try_i in xrange(len(backoff)):
            try:
                return requests.get("{}/{}/{}/{}{}".format(self._query_url, QUERY_APINAMESPACE, QUERY_APINAME, self.apiversion, url))
            except Exception as e:
                self.logger.writeWarning("Could not GET from query service at {}{}: {}".format(self._query_url, url, e))
                if try_i == len(backoff) - 1:
                    raise QueryNotFoundError(e)

                self._query_url = self.mdns_bridge.getHref(QUERY_MDNSTYPE, self.priority)
                self.logger.writeInfo("Trying query at: {}".format(self._query_url))

        # Shouldn't get this far, but don't return None
        raise QueryNotFoundError("Could not find a query service (should be unreachable!)")

    def get_services(self, service_urn):
        """
        Look for nodes which contain a particular service type.
        Returns a list of found service objects, or an empty list on not-found.
        May raise a QueryNotFound exception if query service can't be contacted.
        """
        response = self._get_query("/nodes/")
        if response.status_code != 200:
            self.logger.writeError("Could not get /nodes/ from query service at {}".format(self._query_url))
            return []

        nodes = response.json()
        services = itertools.chain.from_iterable([n.get('services', []) for n in nodes])
        return [s for s in services if s.get('type', 'unknown') == service_urn]

    def subscribe_topic(self, topic, on_event, on_open=None):
        """
        Subscribe to a query service topic, calling `on_event` for changes.
        Will block unless wrapped in a gevent greenlet:
            gevent.spawn(qs.subscribe_topic, "flows", on_event)
        If `on_open` is given, it will be called when the websocket is opened.
        """
        query_url = self.mdns_bridge.getHref(QUERY_MDNSTYPE, self.priority)
        query_url = query_url + "/" + QUERY_APINAMESPACE + "/" + QUERY_APINAME + "/" + self.apiversion

        if query_url == "":
            raise BadSubscriptionError("Could not get query service from mDNS bridge")

        resource_path = "/" + topic.strip("/")
        params = {"max_update_rate_ms": 100, "persist": False, "resource_path": resource_path, "params": {}}
        r = requests.post(query_url + "/subscriptions", data=json.dumps(params), proxies={'http': ''})
        if r.status_code not in [200, 201]:
            raise BadSubscriptionError("{}: {}".format(r.status_code, r.text))

        r_json = r.json()
        if not "ws_href" in r_json:
            raise BadSubscriptionError("Result has no 'ws_href': {}".format(r_json))

        assert(query_url.startswith("http://"))
        ws_href = r_json.get("ws_href")

        # handlers for websocket events
        def _on_open(*args):
            if on_open is not None:
                on_open()

        def _on_close(*args):
            pass

        def _on_message(*args):
            assert(len(args) >= 1)
            data = json.loads(args[1])
            events = data["grain"]["data"]
            if isinstance(events, dict):
                events = [events]
            for event in events:
                on_event(event)

        # Open websocket connection, and poll
        sock = websocket.WebSocketApp(ws_href, on_open=_on_open, on_message=_on_message, on_close=_on_close)
        if sock is None:
            raise BadSubscriptionError("Could not open websocket at {}".format(ws_href))

        sock.run_forever()

if __name__ == '__main__':
    from nmoscommon.mdnsbridge import IppmDNSBridge

    qs = QueryService(IppmDNSBridge())

    print qs.get_services("urn:x-nmos-opensourceprivatenamespace:service:status/v1.0")
    print qs.get_services("urn:x-nmos-opensourceprivatenamespace:service:storedflowquery/v2.0")
    print qs.get_services("urn:x-nmos-opensourceprivatenamespace:service:fake/v1.0")

    def callback(data):
        print "\n----\n", data

    def on_open():
        print "ONOPEN"

    gevent.spawn(qs.subscribe_topic, "nodes", callback, on_open)

    while True:
        gevent.sleep(1)
