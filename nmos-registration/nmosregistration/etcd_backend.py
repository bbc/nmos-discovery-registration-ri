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

import requests
import json
import gevent
import urllib

from etcd_util import etcd_unpack

from requests.adapters import TimeoutSauce

# Set global timeout
class MyTimeout(TimeoutSauce):
    def __init__(self, *args, **kwargs):
        connect = kwargs.get('connect', 0.5)
        read = kwargs.get('read', connect)
        super(MyTimeout, self).__init__(connect=connect, read=read)

requests.adapters.TimeoutSauce = MyTimeout

def _prune_empty_branches(key, port=4001):
    """
    Given KEY, delete any empty "dir" nodes.
    e.g. if key = a/b/c/d, delete c, b, and a if they are empty "dirs".
    """
    parent_keys = [k for k in key.split("/") if len(k) > 0]
    while len(parent_keys) > 1:
        parent_keys = parent_keys[:-1]
        k = "/".join(parent_keys)
        url = "http://localhost:{}/v2/keys/{}".format(port, k)
        r = requests.get(url, proxies={'http': ''})
        if r.status_code == 200:
            obj = r.json().get("node", {})
            if obj.get("dir", False):
                if "nodes" not in obj or len(obj["nodes"]) == 0:
                    requests.delete("{}?dir=true".format(url), proxies={'http': ''})


class EtcdInterface(object):

    class RegistryUnavailable(Exception):
        pass

    # TODO: there is a lot of generality in the below...

    def put(self, rtype, rkey, value, ttl=None, port=4001):
        assert(rtype.endswith('s'))   # ensure that type is pluralised
        data = { "value": value }
        if ttl: data['ttl'] = ttl
        headers = {"content-type": "application/x-www-form-urlencoded"}
        url = "http://localhost:{}/v2/keys/resource/{}/{}".format(port, rtype, rkey)
        try:
            r = requests.put(url, urllib.urlencode(data), headers=headers, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        return r

    def delete(self, rtype, rkey, port=4001):
        assert(rtype.endswith('s'))   # ensure that type is pluralised
        url = "http://localhost:{}/v2/keys/resource/{}/{}?recursive=true".format(port, rtype, rkey)
        try:
            r = requests.delete(url, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        return r

    def getresources(self, rtype, port=4001):
        assert(rtype.endswith('s'))   # ensure that type is pluralised
        url = "http://localhost:{}/v2/keys/resource/{}".format(port, rtype)
        try:
            etcd_nodes = requests.get(url, proxies={'http': ''}).json().get('node', {'nodes' : []}).get('nodes', [])
            keys = [ x['key'].split('/')[-1] for x in etcd_nodes if 'key' in x ]
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        return keys

    def get(self, rtype, rkey, port=4001):
        assert(rtype.endswith('s'))   # ensure that type is pluralised
        url = "http://localhost:{}/v2/keys/resource/{}/{}?recursive=true".format(port, rtype, rkey)
        try:
            r = requests.get(url, proxies={'http': ''}).json().get('node', {'value' : None}).get('value', None)
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        if r is None:
            return
        else:
            return json.loads(r)

    def get_all(self, rtype, port=4001):
        try:
            assert(rtype.endswith('s'))   # ensure that type is pluralised
            url = "http://localhost:{}/v2/keys/resource/{}/?recursive=true".format(port, rtype)
            r = requests.get(url, proxies={'http': ''}).json()
            resources = r.get('node', {}).get('nodes', [])
            return [json.loads(x.get('value')) for x in resources]

        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable

    ## Health

    def put_health(self, rkey, value, ttl=None, port=4001):
        data = { "value": value }
        if ttl: data['ttl'] = ttl
        headers = {"content-type": "application/x-www-form-urlencoded"}
        url = "http://localhost:{}/v2/keys/health/{}".format(port, rkey)
        try:
            r = requests.put(url, urllib.urlencode(data), headers=headers, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        return r

    def get_healths(self, port=4001):
        url = "http://localhost:{}/v2/keys/health/?recursive=true".format(port)
        try:
            r = requests.get(url, proxies={'http': ''})
            return etcd_unpack(r.json())
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable

    def get_health(self, rkey, port=4001):
        url = "http://localhost:{}/v2/keys/health/{}/?recursive=true".format(port,rkey)
        try:
            r = requests.get(url, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable

        if r is None:
            return None
        return r.json().get("node",{}).get("value", None)

    def put_garbage_collection_flag(self, host, ttl, port=4001):
        # See https://github.com/coreos/etcd/blob/master/Documentation/api.md#atomic-compare-and-swap
        url = "http://127.0.0.1:{}/v2/keys/garbage_collection?prevExist=false".format(port)
        data = "value={}&ttl={}".format(host, ttl)
        headers = {"content-type": "application/x-www-form-urlencoded"}
        return requests.put(url, data=data, headers=headers)

    # TODO: a lot could be re-cast to use this
    def put_raw(self, rkey, value, ttl=None, port=4001):
        data = { "value": value }
        if ttl: data['ttl'] = ttl
        headers = {"content-type": "application/x-www-form-urlencoded"}
        url = "http://localhost:{}/v2/keys/{}".format(port, rkey)
        try:
            r =  requests.put(url, urllib.urlencode(data), headers=headers, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
        return r

    def delete_raw(self, rkey, port=4001):
        url = "http://localhost:{}/v2/keys/{}?recursive=true".format(port, rkey)
        try:
            r =  requests.delete(url, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable

        # Experimental: etcd leaves empty dirs around, so spawn a background task to delete them.
        gevent.spawn(_prune_empty_branches, rkey)

        return r

    def get_raw(self, rkey, recurse=True, port=4001):
        url = "http://localhost:{}/v2/keys/{}?recursive={}".format(port, rkey, "true" if recurse else "false")
        try:
            return requests.get(url, proxies={'http': ''})
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable

    def resource_exists(self, resource_type, resource_id, port=4001):
        """Test if a resource exists in the datastore"""
        url = "http://localhost:{}/v2/keys/resource/{}/{}".format(port, resource_type, resource_id)
        try:
            response = requests.head(url, proxies={'http': ''})
            return response.status_code == 200
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            raise self.RegistryUnavailable
