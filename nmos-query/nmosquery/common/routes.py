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

import json

from functools import wraps
from nmoscommon.webapi import on_json, route
from flask import request, abort
from socket import error as socket_error
from nmosquery import VALID_TYPES
from nmosquery.common.query import QueryCommon

class RoutesCommon(object):

    def __init__(self, logger, api_version="v1.0"):
        self.logger = logger
        self.query = QueryCommon(logger=self.logger)
        self.on_websocket_connect = self.websocket_opened
        self.api_version = api_version

    @route('/')
    def __versionindex(self):
        obj = ["subscriptions/"]
        for nmos_type in VALID_TYPES:
            obj.append(nmos_type+"/")
        return (200, obj)

    @route('/<nmos_type>/')
    def __nmos_type(self, nmos_type):
        self.logger.writeDebug('nmos_type')
        if nmos_type not in VALID_TYPES:
            abort(404)
        obj = self.query.get_data_for_path('/{}'.format(nmos_type), request.args)
        self.logger.writeDebug('obj {}'.format(obj))
        if not obj:
            obj = []
        return (200, obj)

    @route('/<nmos_type>/<el_id>/')
    def __el_id(self, nmos_type, el_id):
        if nmos_type not in VALID_TYPES:
            abort(404)
        obj = self.query.get_data_for_path('/{}/{}'.format(nmos_type, el_id), request.args)
        if not obj:
            return(404, '')
        if isinstance(obj, list) and len(obj) >= 1:
            obj = obj[0]
        return (200, obj)

    @route('/subscriptions', methods=['POST'])
    def __subscriptions_post(self):
        try:
            data = json.loads(request.data)
        except ValueError:
            abort(400, "No data supplied")
        obj, created = self.query.post_ws_subscribers(data)
        return (201 if created else 200, obj)

    @route('/subscriptions/', methods=['GET'])
    def __subscriptions_get(self):
        obj = self.query.get_ws_subscribers()
        return (200, obj)

    @route('/subscriptions/<socket_id>', methods=['GET', 'DELETE'])
    def __subscriptions_id(self, socket_id):
        self.logger.writeDebug('subscriptions')
        obj = self.query.get_ws_subscribers(socket_id)

        if request.method == 'DELETE' and obj:
            ret = self.query.delete_ws_subscribers(socket_id)
            if ret:
                return (204, None)
            else:
                abort(403, "Not a persistent websocket")
        elif not obj:
            abort(404, "Subscription not found")

        return (200, obj)

    @on_json('/ws/')
    def __ws(self, ws):
        self.logger.writeInfo("{} ws {}".format(self.api_version, ws))
        return

    def websocket_opened(self, handler_func):
        @wraps(handler_func)
        def inner_func(ws):
            ws_args_str = ws.environ['QUERY_STRING']
            (_, query_args) = self.query.query_sockets.parse_env_str(ws_args_str)
            uid = query_args.get('uid', None)
            self.logger.writeDebug('handle_sock for ID ' + uid)

            # does sock exist
            socket = self.query.query_sockets.get_sock({'uuid': uid})
            if not socket:
                self.logger.writeError('handle_sock: socket does not exist: {}'.format(uid))
                return

            # register client on socket
            self.logger.writeDebug("new subscriber on ws {} ({})".format(uid, ws))
            socket.add_subscriber(ws)

            # do a sync
            self.query.do_sync(ws, socket)

            # recv code
            message = None
            while True:
                try:
                    message = ws.receive()

                except socket_error:
                    message = None

                except Exception as ex:
                    self.logger.writeError("ws recv: unexpected exception: {}".format(ex))
                    message = None

                if message is not None:
                    # call the 'on_json' route
                    handler_func(ws, message)

                else:
                    # gevent-websockets states that None from receive() means "closed or errored"
                    # reduce count of subscribers, if it hits zero, remove the socket.
                    # inlining this functionality here rather than hiding it elsewhere
                    # to make it easier to un-pick when the time comes...
                    socket.subscribers.remove(ws)
                    self.logger.writeDebug("Removed subscription to {}: {} left".format(uid, len(socket.subscribers)))
                    if not socket.subscribers:
                        if socket in self.query.query_sockets.sockets:
                            if socket.persist:
                                self.logger.writeDebug("Leaving persistent socket {} in place.".format(uid))
                            else:
                                self.logger.writeDebug("Removing socket {} for good.".format(uid))
                                self.query.query_sockets.sockets.remove(socket)
                        else:
                            self.logger.writeError("Should have found socket {} in query_sockets, didn't. Investigate.".format(uid))

                    break

        return inner_func
