#! /usr/bin/python

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

import unittest
import requests
import threading

from nmoscommon.webapi import WebAPI, route, abort
from nmoscommon.logger import Logger
from nmoscommon.utils import getLocalIP

HOST = getLocalIP()
logger = Logger(__name__)


class MockAPI(WebAPI):

    def __init__(self):
        super(MockAPI, self).__init__()

    @route('/error', methods=["HEAD", "GET"])
    def _error(self):
        abort(400, "some error")

    @route('/internal_error', methods=["HEAD", "GET"])
    def _internal_error(self):
        raise Exception("Uh oh")

    @route('/json')
    def _json(self):
        return {'a': 1, 'b': [2, 'three']}

    @route('/tuple', methods=['GET', 'HEAD'], auto_json=False)
    def _tuple(self):
        return ("ok", 200)


class MockService(threading.Thread):
    daemon = True

    def __init__(self):
        threading.Thread.__init__(self)
        self.api = MockAPI()

    def run(self):
        self.api.app.run(port=5555)

    def stop(self):
        pass


class FacadeProxyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._srv = MockService()
        cls._srv.start()

    def assert_has_cors(self, response):
        self.assertIn('Access-Control-Allow-Origin', response.headers)
        self.assertIn('Access-Control-Allow-Methods', response.headers)
        self.assertIn('Access-Control-Max-Age', response.headers)
        self.assertIn('Access-Control-Allow-Headers', response.headers)

    def test_error_get(self):
        response = requests.get("http://localhost:5555/error")
        self.assertEqual(400, response.status_code)
        self.assertEqual("application/json", response.headers.get('Content-Type'))
        response_content = response.json()
        self.assertEqual("some error", response_content['error'])
        self.assert_has_cors(response)

    def test_error_head(self):
        response = requests.head("http://localhost:5555/error")
        self.assertEqual(400, response.status_code)
        self.assertEqual("0", response.headers.get('Content-Length'))
        self.assertEqual("", response.text)
        self.assert_has_cors(response)

    def test_auto_json(self):
        response = requests.get("http://localhost:5555/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual("application/json", response.headers.get('Content-Type'))
        self.assertEqual({'a': 1, 'b': [2, 'three']}, response.json())
        self.assert_has_cors(response)

    def test_internal_error_get(self):
        response = requests.get("http://localhost:5555/internal_error")
        self.assertEqual(500, response.status_code)
        response_content = response.json()
        self.assertEqual(500, response_content['code'])
        self.assertEqual("Internal Error", response_content['error'])
        self.assertEqual(["Exception: Uh oh\n"], response_content['debug']['exception'])
        self.assert_has_cors(response)

    def test_internal_error_head(self):
        response = requests.head("http://localhost:5555/internal_error")
        self.assertEqual(500, response.status_code)
        self.assertEqual("0", response.headers.get('Content-Length'))
        self.assertEqual("", response.text)
        self.assert_has_cors(response)

    def test_no_json_tuple(self):
        response = requests.get("http://localhost:5555/tuple")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.text)
        self.assertEqual("text/html; charset=utf-8", response.headers.get('Content-Type'))
        self.assert_has_cors(response)

    def test_head(self):
        response = requests.head("http://localhost:5555/tuple")
        self.assertEqual(200, response.status_code)
        self.assertEqual("", response.text)
        self.assertEqual("2", response.headers.get('Content-Length'))
        self.assertEqual("text/html; charset=utf-8", response.headers.get('Content-Type'))
        self.assert_has_cors(response)

if __name__ == '__main__':
    unittest.main()
