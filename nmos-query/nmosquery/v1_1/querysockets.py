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

from nmosquery.common.querysockets import QuerySocketCommon, QuerySocketsCommon, QueryFilterCommon

class QuerySocket(QuerySocketCommon):
    def __init__(self, resource_path, ws_port, rate=100, persist=False, params=None, secure=False, logger=None):
        super(QuerySocket, self).__init__(resource_path, ws_port, rate, persist, params, logger, "v1.1")
        self.secure = secure

class QuerySockets(QuerySocketsCommon):
    def __init__(self, ws_port, logger=None):
        super(QuerySockets, self).__init__(ws_port, logger)

    # add a socket
    def add_sock(self, opts):
        sock = QuerySocket(rate=opts.get('max_update_rate_ms', 100),
                           ws_port=self.ws_port,
                           persist=opts.get('persist', False),
                           resource_path=opts.get('resource_path', ''),
                           params=opts.get('params', {}),
                           logger=self.logger)
        self.sockets.append(sock)
        self.logger.writeDebug('Number of active sockets: {}'.format(len(self.sockets)))
        return sock

    def _check_args(self, s, obj):
        arg_checker = QueryFilter()
        return arg_checker.check_args(s.params, obj)

    # summarise service in a presentable way
    def _summarise(self, obj):
        retval = super(QuerySockets, self)._summarise(obj)
        retval['secure'] = obj.secure
        return retval

class QueryFilter(QueryFilterCommon):
    def __init__(self):
        super(QueryFilter, self).__init__()
