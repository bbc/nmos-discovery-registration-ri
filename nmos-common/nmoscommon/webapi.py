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

import uuid
import json
import traceback

from flask import Flask, Response, request, abort, jsonify
from flask_sockets import Sockets
from nmoscommon.flask_cors import crossdomain
from functools import wraps
from utils import getLocalIP
import re

from pygments import highlight
from pygments.lexers import JsonLexer, PythonTracebackLexer
from pygments.formatters import HtmlFormatter
import urlparse
import sys

from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import BaseResponse

from requests.structures import CaseInsensitiveDict

import flask_oauthlib

try:
    from urlparse import urlparse
    import urllib2 as http
except ImportError:
    from urllib import request as http
    from urllib.parse import urlparse


HOST = getLocalIP()

class LinkingHTMLFormatter(HtmlFormatter):
    def wrap(self, source, outfile):
        return self._wrap_linking(super(LinkingHTMLFormatter, self).wrap(source, outfile))

    def _wrap_linking(self, source):
        for i, t in source:
            m = re.match(r'(.*)&quot;([a-zA-Z0-9_.\-~]+)/&quot;(.+)', t)
            if m:
                t = m.group(1) + '&quot;<a href="' + m.group(2) + '/">' + m.group(2) + '/</a>&quot;' + m.group(3) + "<br>"

            yield i, t

def htmlify(r, mimetype, status=200):

    # if the request was proxied via the nodefacade, use the original host in response.
    # additional external proxies could cause an issue here...
    path = request.headers.get('X-Forwarded-Path', request.path)
    host = request.headers.get('X-Forwarded-Host', request.host)
    scheme = request.headers.get('X-Forwarded-Proto', urlparse(request.url).scheme)
    base_url = "{}://{}".format(scheme, host)

    title = '<a href="' + base_url + '/">' + base_url + '</a>'
    t = base_url
    for x in path.split('/'):
        if x != '':
            t += '/' + x.strip('/')
            title += '/<a href="' + t + '">' + x.strip('/') + '</a>'
    return IppResponse(highlight(json.dumps(r, indent=4),
                                 JsonLexer(),
                                 LinkingHTMLFormatter(linenos='table',
                                                     full=True,
                                                     title=title)),
                       mimetype='text/html',
                       status=status)

def jsonify(r, status=200, headers=None):
    if headers == None:
        headers = {}
    return IppResponse(json.dumps(r, indent=4),
                       mimetype='application/json',
                       status=status,
                       headers=headers)

def returns_response(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)

        response = r.response
        status = r.status_code
        headers = dict(r.headers)
        mimetype = r.mimetype
        content_type = r.content_type
        direct_passthrough = True

        return IppResponse(response=response, status=status, headers=headers, mimetype=mimetype, content_type=content_type, direct_passthrough=direct_passthrough)
    return decorated_function

def returns_json(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        status = 200
        flatfmt = False
        headers = {}
        if isinstance(r, tuple) and len(r) > 1:
            status = r[0]
            if len(r) > 2:
                headers = r[2]
            r = r[1]
        if isinstance(r, list):
            flatfmt = True
        if isinstance(r, dict) or flatfmt:
            try:
                bm = request.accept_mimetypes.best_match(['application/json', 'text/html', 'rick/roll'])
                if bm in ['text/html', 'rick/roll']:
                    return htmlify(r, bm, status=status)
                else:
                    return jsonify(r, status=status, headers=headers)
            except TypeError:
                if status == 200:
                    status = 204
                return IppResponse(status=status)
        else:
            return IppResponse(r, status=status, headers=headers)
    return decorated_function

def returns_requires_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)

        if f.im_self._oauth_config is not None:
            if 'token' not in request.headers:
                print 'Could not find token'
                return IppResponse(status=401)

            token = request.headers.get('token')
            if not f.im_self._authenticate(token):
                print 'Authentication Failed'
                return IppResponse(status=401)

            if not f.im_self._authorize(token):
                print 'Authorization Failed.'
                return IppResponse(status=401)

        status = 200
        flatfmt = False
        headers = {'Access-Control-Allow-Credentials': 'true'}
        if isinstance(r, tuple) and len(r) > 1:
            status = r[0]
            if len(r) > 2:
                headers = r[2]
            r = r[1]
        if isinstance(r, list):
            flatfmt = True
        if isinstance(r, dict) or flatfmt:
            try:
                bm = request.accept_mimetypes.best_match(['application/json', 'text/html', 'rick/roll'])
                if bm in ['text/html', 'rick/roll']:
                    return htmlify(r, bm, status=status)
                else:
                    return jsonify(r, status=status, headers=headers)
            except TypeError:
                if status == 200:
                    status = 204
                return IppResponse(status=status)
        elif isinstance(r, BaseResponse):
            headers = r.headers
            headers['Access-Control-Allow-Credentials'] = 'true'
            if isinstance(r, IppResponse):
                return r
            else:
                return IppResponse(response=r.response, status=r.status, headers=headers, mimetype=r.mimetype, content_type=r.content_type, direct_passthrough=r.direct_passthrough)
        else:
            return IppResponse(response=r, status=status, headers=headers)

    return decorated_function

def returns_file(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        if 'content-type' in r and r['content-type'] is not None:
            return IppResponse(r['content'], status=200, headers={'Content-Disposition': 'attachment; filename={}.{}'.format(r['filename'], r['type'])}, content_type=r['content-type'])
        else:
            return IppResponse(r['content'], status=200, headers={'Content-Disposition': 'attachment; filename={}.{}'.format(r['filename'], r['type'])})

    return decorated_function

def obj_path_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        path = kwargs.pop('path', '')
        rep = f(*args, **kwargs)
        if request.method == "GET":
            p = [ x for x in path.split('/') if x != '' ]
            for x in p:
                if isinstance(rep, dict):
                    if x not in rep:
                        abort(404)
                    rep = rep[x]
                elif isinstance(rep, list) or isinstance(rep, tuple):
                    try:
                        y = int(x)
                    except:
                        abort(404)
                    if y < 0 or y >= len(rep):
                        abort(404)
                    rep = rep[y]
                else:
                    abort(404)
            repdump = json.dumps(rep)
            if repdump == "{}":
                return []
            else:
                return rep
        else:
            return rep
    return decorated_function

def secure_route(path, methods=None, auto_json=True, headers=None, origin='*'):
    if methods is None:
        methods = ['GET', 'HEAD']
    if headers is None:
        headers = []

    def annotate_function(func):
        func.secure_route = path
        func.app_methods = methods
        func.app_auto_json = auto_json
        func.app_headers = headers
        func.app_origin = origin
        return func
    return annotate_function

def basic_route(path):
    def annotate_function(func):
        func.response_route = path
        return func
    return annotate_function

def route(path, methods=None, auto_json=True, headers=None, origin='*'):
    if headers == None:
        headers = []
    def annotate_function(func):
        func.app_route = path
        func.app_methods = methods
        func.app_auto_json = auto_json
        func.app_headers = headers
        func.app_origin = origin
        return func
    return annotate_function

def resource_route(path, methods=None):
    def annotate_function(func):
        func.app_resource_route = path
        func.app_methods = methods
        return func
    return annotate_function

def file_route(path, methods=None, headers=None):
    def annotate_function(func):
        func.app_file_route = path
        func.app_methods = methods
        func.app_headers = headers
        return func
    return annotate_function

def errorhandler(*args,**kwargs):
    def annotate_function(func):
        func.errorhandler_args = args
        func.errorhandler_kwargs = kwargs
        return func
    return annotate_function

def on_json(path):
    def annotate_function(func):
        @wraps(func)
        def inner_func(self, ws, message):
            return func(self, ws, json.loads(message))
        inner_func.sockets_on = path
        return inner_func
    return annotate_function


def wrap_val_in_grain(pval):
    egrain = {
            "grain": {
                "duration": {
                    "denominator": 1,
                    "numerator": 0
                    },
                "flow_id": "00000000-0000-0000-0000-000000000000",
                "grain_type": "event",
                "source_version": 0,
                "rate": {
                    "denominator": 1,
                    "numerator": 0
                    },
                "origin_timestamp": "0:0",
                "source_id": "00000000-0000-0000-0000-000000000000",
                "sync_timestamp": "0:0",
                "creation_timestamp": "0:0",
                "event_payload": {
                    "type": "urn:x-nmos-opensourceprivatenamespace:format:event.param.change",
                    "topic": "",
                    "data": [
                        {
                            "path":{},
                            "pre":{},
                            "post":{}
                        }
                    ]
                },
                "flow_instance_id": "00000000-0000-0000-0000-000000000000"
                },
            "@_ns": "urn:x-nmos-opensourceprivatenamespace:ns:0.1"
            }
    egrain["grain"]["event_payload"]["data"][0]["post"] = pval
    return json.dumps(egrain)

def grain_event_wrapper(func):
    @wraps(func)
    def wrapper(self, ws, message):
        pval = func(self, ws, message["grain"]["event_payload"]["data"][0]["post"])
        if pval is not None:
            ws.send(wrap_val_in_grain(pval))
    return wrapper

class IppResponse(Response):
    def __init__(self, response=None, status=None, headers=None, mimetype=None, content_type=None, direct_passthrough=False):
        headers = CaseInsensitiveDict(headers) if headers is not None else None
        if response is not None and isinstance(response, BaseResponse):
            headers = CaseInsensitiveDict(response.headers)

        if headers is None:
            headers = CaseInsensitiveDict()

        h = headers
        h['Access-Control-Allow-Origin'] = headers.get('Access-Control-Allow-Origin', '*')
        h['Access-Control-Allow-Methods'] = headers.get('Access-Control-Allow-Methods', "GET, PUT, POST, HEAD, OPTIONS, DELETE")
        h['Access-Control-Max-Age'] = headers.get('Access-Control-Max-Age', "21600")
        h['Cache-Control'] = headers.get('Cache-Control', "no-cache, must-revalidate, no-store")
        if 'Access-Control-Allow-Headers' not in headers and len(headers.keys()) > 0:
            h['Access-Control-Allow-Headers'] = ', '.join(headers.iterkeys())

        if response is not None and isinstance(response, BaseResponse):
            new_response_headers = CaseInsensitiveDict(response.headers if response.headers is not None else {})
            new_response_headers.update(h)
            response.headers = new_response_headers
            headers = None

        else:
            headers.update(h)

        super(IppResponse, self).__init__(response=response,
                                          status=status,
                                          headers=dict(headers),
                                          mimetype=mimetype,
                                          content_type=content_type,
                                          direct_passthrough=direct_passthrough)


def proxied_request(uri, headers=None, data=None, method=None, proxies=None):
    uri, headers, data, method = flask_oauthlib.client.prepare_request(uri, headers, data, method)
    proxy = http.ProxyHandler(proxies)
    opener = http.build_opener(proxy)
    http.install_opener(opener)
    flask_oauthlib.client.log.debug('Request %r with %r method' % (uri, method))
    req = http.Request(uri, headers=headers, data=data)
    req.get_method = lambda: method.upper()
    try:
        resp = http.urlopen(req)
        content = resp.read()
        resp.close()
        return resp, content
    except http.HTTPError as resp:
        content = resp.read()
        resp.close()
        return resp, content


class WebAPI(object):
    def __init__(self, oauth_config=None):
        self.app = Flask(__name__)
        self.app.response_class = IppResponse
        self.app.before_first_request(self.torun)
        self.sockets = Sockets(self.app)
        self.socks = dict()
        self.port = 0

        # authentication/authorisation
        self._oauth_config = oauth_config
        self._authorize = self.default_authorize
        self._authenticate = self.default_authenticate

        self.add_routes(self, basepath='')

    def add_routes(self, cl, basepath):

        assert not basepath.endswith('/'), "basepath must not end with a slash"

        def dummy(f):
            @wraps(f)
            def inner(*args, **kwargs):
                return f(*args, **kwargs)
            return inner

        def getbases(cl):
            bases = list(cl.__bases__)
            for x in cl.__bases__:
                bases += getbases(x)
            return bases

        for klass in [cl.__class__,] + getbases(cl.__class__):
            for name in klass.__dict__.keys():
                value = getattr(cl, name)
                if callable(value):
                    endpoint = "{}_{}".format(basepath.replace('/', '_'), value.__name__)
                    if hasattr(value, "secure_route"):
                        self.app.route(
                            basepath + value.secure_route,
                            endpoint=endpoint,
                            methods=value.app_methods + ["OPTIONS"])(crossdomain(
                                origin=value.app_origin,
                                methods=value.app_methods,
                                headers=value.app_headers +
                                ['Content-Type',
                                 'token',])(returns_requires_auth(value)))
                    elif hasattr(value, "response_route"):
                        self.app.route(
                            basepath + value.response_route,
                            endpoint=endpoint,
                            methods=["GET", "POST", "HEAD", "OPTIONS"])(crossdomain(
                                origin='*',
                                methods=['GET', 'POST', 'HEAD'],
                                headers=['Content-Type',])(returns_response(value)))
                    elif hasattr(value, "app_route"):
                        if value.app_auto_json:
                            if value.app_methods:
                                self.app.route(
                                    basepath + value.app_route,
                                    endpoint=endpoint,
                                    methods=value.app_methods +
                                    ["OPTIONS",])(crossdomain(
                                        origin=value.app_origin,
                                        methods=value.app_methods,
                                        headers=value.app_headers +
                                        ["Content-Type",])(returns_json(value)))
                            else:
                                self.app.route(
                                    basepath + value.app_route,
                                    endpoint=endpoint,
                                    methods=["GET", "HEAD", "OPTIONS"])(crossdomain(
                                        origin=value.app_origin,
                                        methods=["GET", "HEAD"],
                                        headers=value.app_headers +
                                        ["Content-Type",])(returns_json(value)))
                        else:
                            if value.app_methods:
                                self.app.route(
                                    basepath + value.app_route,
                                    endpoint=endpoint,
                                    methods=value.app_methods +
                                    ["OPTIONS",])(crossdomain(
                                        origin=value.app_origin,
                                        methods=value.app_methods,
                                        headers=["Content-Type",])(dummy(value)))
                            else:
                                self.app.route(
                                    basepath + value.app_route,
                                    endpoint=endpoint,
                                    methods=["GET", "HEAD", "OPTIONS"])(crossdomain(
                                        origin=value.app_origin,
                                        methods=["GET", "HEAD"],
                                        headers=["Content-Type",])(dummy(value)))
                    elif hasattr(value, "app_file_route"):
                        self.app.route(
                            basepath + value.app_file_route,
                            endpoint=endpoint,
                            methods=value.app_methods)(crossdomain(
                                origin='*',
                                methods=['GET', 'HEAD'],
                                headers=['Content-Type',])(returns_file(value)))
                    elif hasattr(value, "app_resource_route"):
                        if value.app_methods:
                            f = crossdomain(origin='*',
                                            methods=value.app_methods,
                                            headers=["Content-Type",
                                                     "api-key",])(returns_json(
                                                         obj_path_access(value)))
                            self.app.route(basepath + value.app_resource_route,
                                           methods=value.app_methods + ["OPTIONS",],
                                           endpoint=endpoint)(f)
                            f.__name__ = endpoint + '_path'
                            self.app.route(
                                basepath + value.app_resource_route + '<path:path>/',
                                methods=value.app_methods + ["OPTIONS",],
                                endpoint=f.__name__)(f)
                        else:
                            f = crossdomain(origin='*',
                                            methods=["GET", "HEAD"],
                                            headers=["Content-Type",
                                                     "api-key",])(returns_json(
                                                         obj_path_access(value)))
                            self.app.route(basepath + value.app_resource_route,
                                           methods=["GET", "HEAD", "OPTIONS"],
                                           endpoint=f.__name__)(f)
                            f.__name__ = endpoint + '_path'
                            self.app.route(
                                basepath + value.app_resource_route + '<path:path>/',
                                methods=["GET", "HEAD", "OPTIONS"],
                                endpoint=f.__name__)(f)
                    elif hasattr(value, "sockets_on"):
                        socket_recv_gen = getattr(cl, "on_websocket_connect", None)
                        if socket_recv_gen is None:
                            f = self.handle_sock(value, self.socks)
                        else:
                            f = socket_recv_gen(value)
                        self.sockets.route(basepath + value.sockets_on, endpoint=endpoint)(f)
                    elif hasattr(value, "errorhandler_args"):
                        if value.errorhandler_args:
                            self.app.errorhandler(
                                *value.errorhandler_args, **
                                value.errorhandler_kwargs)(crossdomain(
                                    origin='*',
                                    methods=["GET", "POST", "PUT", "DELETE",
                                             "OPTIONS", "HEAD"])(dummy(value)))
                        else:
                            for n in range(400, 600):
                                self.app.errorhandler(n)(crossdomain(
                                    origin='*',
                                    methods=["GET", "POST", "PUT", "DELETE",
                                             "OPTIONS", "HEAD"])(dummy(value)))

    @errorhandler(301)
    def __redirect(self, e):
        return e.get_response(request.environ)

    @errorhandler()
    def error(self, e):
        if request.method == 'HEAD':
            if isinstance(e, HTTPException):
                return IppResponse('', status=e.code)
            else:
                return IppResponse('', 500)

        bm = request.accept_mimetypes.best_match(['application/json', 'text/html'])
        if bm == 'text/html':
            if isinstance(e,HTTPException):
                if e.code == 400:
                    (t,v,tb) = sys.exc_info()
                    return IppResponse(highlight('\n'.join(traceback.format_exception(t,v,tb)), PythonTracebackLexer(), HtmlFormatter(linenos='table',
                                                                                                                                      full=True,
                                                                                                                                      title="{}: {}".format(e.code, e.description))),
                        status=e.code,
                        mimetype='text/html')
                return e.get_response()

            (t,v,tb) = sys.exc_info()
            return IppResponse(highlight('\n'.join(traceback.format_exception(t,v,tb)), PythonTracebackLexer(), HtmlFormatter(linenos='table',
                                                                                                                              full=True,
                                                                                                                              title='500: Internal Exception')),
                            status=500,
                            mimetype='text/html')
        else:
            t, v, tb = sys.exc_info()
            if isinstance(e, HTTPException):
                response = {
                    'code': e.code,
                    'error': e.description,
                    'debug': {
                        'traceback': [x for x in traceback.extract_tb(tb)],
                        'exception': [x for x in traceback.format_exception_only(t, v)]
                    }
                }

                return IppResponse(json.dumps(response), status=e.code, mimetype='application/json')

            response = {
                'code': 500,
                'error': 'Internal Error',
                'debug': {
                    'traceback': [x for x in traceback.extract_tb(tb)],
                    'exception': [x for x in traceback.format_exception_only(t, v)]
                }
            }

            return IppResponse(json.dumps(response), status=500, mimetype='application/json')

    def torun(self):
        pass

    def stop(self):
        pass

    def handle_sock(self, func, socks):
        @wraps(func)
        def inner_func(ws):
            sock_uuid = uuid.uuid4()
            socks[sock_uuid] = ws
            print "Opening Websocket {} at path /, Receiving ...".format(sock_uuid)
            while True:
                try:
                    message = ws.receive()
                except:
                    message = None

                if message is not None:
                    func(ws, message)
                    continue
                else:
                    print "Websocket {} closed".format(sock_uuid)
                    del socks[sock_uuid]
                    break
        return inner_func

    def default_authorize(self, token):
        if self._oauth_config is not None:
            # Ensure the user is permitted to use function
            print('authorizing: {}'.format(token))
            loginserver = self._oauth_config['loginserver']
            proxies = self._oauth_config['proxies']
            whitelist = self._oauth_config['access_whitelist']
            result = proxied_request(uri="{}/check-token".format(loginserver), headers={'token': token}, proxies=proxies)
            json_payload = json.loads(result[1])
            return json_payload['userid'] in whitelist
        else:
            return True

    def default_authenticate(self, token):
        if self._oauth_config is not None:
            # Validate the token that the webapp sends
            loginserver = self._oauth_config['loginserver']
            proxies = self._oauth_config['proxies']
            print('authenticating: {}'.format(token))
            if token is None:
                return False
            result = proxied_request(uri="{}/check-token".format(loginserver), headers={'token': token}, proxies=proxies)
            print('token result code: {}'.format(result[0].code))
            print('result payload: {}'.format(result[1]))
            return result[0].code == 200 and json.loads(result[1])['token'] == token
        else:
            return True

    def authorize(self, f):
        self._authorize = f
        return f

    def authenticate(self, f):
        self._authenticate = f
        return f
