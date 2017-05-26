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

# Classes to manage web sockets

import json
import socket
import uuid

import nmosquery.util as util
from nmoscommon.utils import getLocalIP
from nmoscommon import nmoscommonconfig


class QuerySocketCommon(object):
    def __init__(self, resource_path, ws_port, rate=100, persist=False, params=None, logger=None, api_version="v1.0"):
        if params is None:
            params = {}
        self.logger = logger
        self.uuid = str(uuid.uuid4())
        self.ws_port = ws_port
        self.subscribers = []
        self.api_version = api_version
        self.ws_href = self.gen_ws_href()
        self.resource_path = resource_path
        self.params = params
        self.max_update_rate_ms = rate
        self.persist = persist

    def gen_ws_href(self):
        if nmoscommonconfig.config.get('prefer_ipv6',False) == False:
            href = 'ws://{}/x-nmos/query/{}/ws/?uid={}'.format(getLocalIP(), self.api_version, self.uuid)
        else:
            href = 'ws://[{}]/x-nmos/query/{}/ws/?uid={}'.format(getLocalIP(), self.api_version, self.uuid)
        return href

    def add_subscriber(self, ws):
        self.logger.writeDebug('add_subscriber')
        self.subscribers.append(ws)
        self.logger.writeDebug('There are {} subscribers'.format(len(self.subscribers)))

    def del_subscribers(self):
        for ws in self.subscribers:
            ws.close()
        self.subscribers = []

    def notify_subscribers(self, obj):
        for ws in self.subscribers:
            ws.send(json.dumps(obj))


class QuerySocketsCommon(object):
    def __init__(self, ws_port, logger=None):
        # NB. the 'sockets' here aren't really sockets, but 'QuerySocket' instances from above.
        self.sockets = []
        self.logger = logger
        self.ws_port = ws_port

    # add a socket
    def add_sock(self, opts):
        sock = QuerySocketCommon(rate=opts.get('max_update_rate_ms', 100),
                           ws_port=self.ws_port,
                           persist=opts.get('persist', False),
                           resource_path=opts.get('resource_path', ''),
                           params=opts.get('params', {}),
                           logger=self.logger,
                           api_version=opts.get('api_version', 'v1.0'))
        self.sockets.append(sock)
        self.logger.writeDebug('Number of active sockets: {}'.format(len(self.sockets)))
        return sock

    # delete all sockets
    def del_all_socks(self):
        for sock in self.sockets:
            self.del_sock(sock)

    # delete a socket
    def del_sock(self, sock):
        sock.del_subscribers()
        try:
            self.sockets.remove(sock)
        except ValueError:
            self.logger.writeWarning("del_sock: attempt to remove socket that did not exist")

    def get_sock(self, opts, exclude_persist=False): # exclude_persist causes persistent sockets not to be returned
        for sock in self.sockets:
            proposed_sock = None
            uid = opts.get('uuid', None)
            if uid == sock.uuid:
                proposed_sock = sock
            elif sock.resource_path == opts.get('resource_path', '') and json.dumps(sock.params) == json.dumps(opts.get('params')):
                proposed_sock = sock

            if proposed_sock:
                if not (exclude_persist and proposed_sock.persist):
                    return proposed_sock
        return None

    # Return ws subscribers that are interested in given object
    def find_socks(self, path=None, obj=None, p_obj=None):
        retval = []

        if obj != None:
            # find subscribers for given node

            # eg. path=/dest, args=[label:123]

            # obj = obj[obj.keys()[0]]
            uid = obj.get('uuid', None)
            for s in self.sockets:
                sock_path = util.translate_resourcetypes(s.resource_path)
                matched = True
                if uid == s.uuid:
                    matched = True
                elif sock_path:
                    if sock_path in path:
                        matched = self._check_args(s, obj)
                        if p_obj and not matched:
                            matched = self._check_args(s, p_obj)
                    else:
                        matched = False
                elif not sock_path:   # resource path not defined
                    matched = self._check_args(s, obj)
                    if p_obj and not matched:
                        matched = self._check_args(s, p_obj)
                if matched:
                    retval.append(s)
        return retval

    def _check_args(self, s, obj):
        arg_checker = QueryFilterCommon()
        return arg_checker.check_args(s.params, obj)

    def gen_ws_url(self, path, args):
        argsList = []
        for k, v in args.items():
            argsList.append("{}={}".format(k, v))
        argsStr = '&'.join(argsList)
        if len(argsStr) > 0:
            argsStr = '&' + argsStr
        return '/ws?path={}{}'.format(path, argsStr)

    # Extract path and query arguments from query string
    def parse_env_str(self, ws_args_str):
        ws_path = ''
        query_args = {}
        ws_args = ws_args_str.split('&')
        for arg in ws_args:
            if '=' in arg:
                (k, v) = arg.split('=')
                if k == 'path':
                    ws_path = v
                else:
                    query_args[k] = v
        return (ws_path, query_args)

    def get_socket(self, socket_id):
        retval = None
        sock = self.get_sock({"uuid": socket_id})
        if sock:
            retval = self._summarise(sock)
        return retval

    def get_socketlist(self):
        retval = []
        for sock in self.sockets:
            retval.append(self._summarise(sock))
        return retval

    # Request a socket
    def post_socket(self, json):
        retval = []
        created = False
        socket = self.get_sock(json, exclude_persist=True)
        if not socket or json.get('persist', False):
            socket = self.add_sock(json)
            created = True
        retval = [self._summarise(socket), created]
        return retval

    def delete_socket(self, socket_id):
        socket = self.get_sock({"uuid": socket_id})
        if socket.persist:
            self.del_sock(socket)
            return True
        else:
            return False

    # summarise service in a presentable way
    def _summarise(self, obj):
        retval = {}
        retval['id'] = obj.uuid
        retval['ws_href'] = obj.ws_href
        retval['max_update_rate_ms'] = obj.max_update_rate_ms
        retval['persist'] = obj.persist
        retval['resource_path'] = obj.resource_path
        retval['params'] = obj.params
        return retval


class QueryFilterCommon(object):
    def check_args(self, args, obj):
        matched = True
        if args is None:
            return matched
        for arg_key, val in args.items():
            if arg_key.startswith("query.") or arg_key.startswith("paging."):
                continue
            # Pre-process
            test_data = None
            if arg_key in obj:
                # Test will be on a top level key=value
                test_data = obj[arg_key]
            elif "." in arg_key:
                # Test will be on a nested key.key.key=value
                arg_parts = arg_key.split(".")
                test_data = obj
                for arg_part in arg_parts:
                    if isinstance(test_data, list):
                        # Special case: Deal with nested cases such as Node services, searched by type
                        if len(test_data) == 0:
                            test_data = None
                            matched = False
                            break
                        for child_obj in test_data:
                            if arg_part in child_obj:
                                if child_obj[arg_part] == val:
                                    # We have a match
                                    test_data = child_obj[arg_part]
                                    break
                            else:
                                test_data = None
                                matched = False
                                break
                    elif arg_part in test_data:
                        test_data = test_data[arg_part]
                    else:
                        test_data = None
                        matched = False
                        break
            else:
                matched = False

            if test_data:
                # Perform the test, checking within lists if necessary
                if isinstance(test_data, list):
                    if val not in test_data or len(test_data) == 0:
                        matched = False
                elif test_data != val:
                    matched = False

        return matched
