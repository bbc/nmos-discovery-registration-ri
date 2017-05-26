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

import httplib
import urlparse

def __http(addr, port, method, url, payload=None):
    try:
        # print '==>',method,addr,port,url,payload
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        conn = httplib.HTTPConnection(addr, port)
        conn.request(method, url, payload, headers)
        resp = conn.getresponse()

        # Follow temp redirects
        if resp.status == 307:
            headers = resp.getheaders()
            to = [x[1] for x in resp.getheaders() if x[0] == 'location'][0]
            parts = urlparse.urlparse(to)
            split_netloc = parts.netloc.split(':')

            # Naively assume path stays the same. For our purposes, it does.
            if len(split_netloc) > 1:
                return __http(split_netloc[0], int(split_netloc[1]), method, url, payload)
            else:
                return __http(split_netloc[0], port, method, url, payload)

        resp.data = resp.read() # hack
        # print '<==',resp.status, resp.data, resp.reason, resp.getheaders()
        return resp

    finally:
        conn.close()

def put(key, value, ttl=None, port=4001):
    value = "value={}".format(value)
    if ttl:
      value += "&ttl={}".format(ttl)

    return __http("localhost", port, "PUT", "/v2/keys{}".format(key), value)

def delete(key, port=4001):
    return __http("localhost", port, "DELETE", "/v2/keys{}?recursive=true".format(key))
