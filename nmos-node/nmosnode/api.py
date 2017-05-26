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

from nmoscommon.webapi import *
from urlparse import urlparse, urljoin
import httplib
import requests
from nmoscommon.utils import getLocalIP
from socket import gethostname
from flask import stream_with_context

from nmoscommon import config as _config

NODE_APIVERSIONS = _config.get('nodefacade', {}).get('NODE_APIVERSIONS', [ "v1.0", "v1.1", "v1.2" ])
NODE_REGVERSION = _config.get('nodefacade', {}).get('NODE_REGVERSION', 'v1.1')
NODE_APINAMESPACE = "x-nmos"
NODE_APINAME = "node"
HOSTNAME = gethostname().split(".", 1)[0]

class FacadeAPI(WebAPI):
    def __init__(self, registry):
        self.registry = registry
        self.node_id = registry.node_id
        super(FacadeAPI, self).__init__()

    @route('/')
    def root(self):
        return [NODE_APINAMESPACE+"/"]

    @route('/'+NODE_APINAMESPACE+'/')
    def namespaceroot(self):
        return [NODE_APINAME+"/"]

    @route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/")
    def nameroot(self):
        return [ api_version + "/" for api_version in NODE_APIVERSIONS ]

    @route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/")
    def versionroot(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return ["self/","sources/", "flows/", "devices/", "senders/", "receivers/"]

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/senders/")
    def senders(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return self.registry.list_resource("sender", api_version=api_version).values()

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/receivers/<receiver>/")
    def receiver_id(self, api_version, receiver):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        receivers = self.registry.list_resource("receiver", api_version=api_version)
        if receiver in receivers:
            return receivers[receiver]
        else:
            abort(404)

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/receivers/<receiver_id>/target", methods=['PUT'])
    def receiver_id_subscription(self, api_version, receiver_id):
        if api_version not in NODE_APIVERSIONS:
            abort(404)

        receiver_service = self.registry.find_service("receiver", receiver_id)
        if receiver_service is None:
            abort(404)

        receiver_service_href = self.registry.get_service_href(receiver_service)

        if receiver_service_href is None:
            # Service doesn't specify an href
            return {}
        if str(receiver_service_href).isdigit():
            # Service doesn't exist
            abort(404)
        receiver_subs_href = "receivers/"+receiver_id+"/target"
        href = urljoin(receiver_service_href, receiver_subs_href) + "/"
        #TODO: Handle all request types
        #TODO: Move into proxy class?

        headers = dict(request.headers)
        headers['Accept'] = 'application/json'
        del headers['Host']

        print "Sending {} request to '{}' with headers={} and data='{}'".format(request.method, href, headers, request.data)

        try:
            resp = requests.request(request.method, href, params=request.args, data=request.data, headers=headers, allow_redirects=True, timeout=30)
        except:
            abort(500)

        if not resp:
            abort(503)

        print resp

        if resp.status_code/100 != 2:
            abort(resp.status_code)

        data = {}
        if len(resp.text) > 0:
            data = resp.json()
        else:
            return (204, '')
        if(resp.status_code == 200):
            return (data)
        else:
            return (resp.status_code, data)

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/receivers/")
    def receivers(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return self.registry.list_resource("receiver", api_version=api_version).values()

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/devices/")
    def devices(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return self.registry.list_resource("device", api_version=api_version).values()

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/flows/")
    def flows(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        flows = dict(self.registry.list_resource("flow", api_version=api_version))
        return flows.values()

    @resource_route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/sources/")
    def sources(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return self.registry.list_resource("source", api_version=api_version).values()

    @route('/'+NODE_APINAMESPACE+'/'+NODE_APINAME+"/<api_version>/self/")
    def selfresource(self, api_version):
        if api_version not in NODE_APIVERSIONS:
            abort(404)
        return self.registry.list_self(api_version=api_version)
