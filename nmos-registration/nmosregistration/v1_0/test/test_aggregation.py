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
import time
import json

from nmosregistration.v1_0 import routes as v1_0

from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

REGISTRY_PORT = 4001

class MockLogger():
    def __init__(self):
        self.lines = []

    def writeWarning(self, message):
        self.lines.append(('WARN', message))

    def writeDebug(self, message):
        self.lines.append(('DEBUG', message))

    def writeInfo(self, message):
        self.lines.append(('INFO', message))

    def writeError(self, message):
        print message
        self.lines.append(('ERROR', message))

    def hasLine(self, level, message):
        return (level, message) in self.lines


class MockRegistry():
    def __init__(self):
        self.invocations = []

    class RegistryUnavailable(Exception):
        pass

    def put(self, *args, **kwargs):
        self.invocations.append(('put', args, kwargs))
        return Response('Mock!')

    def put_health(self, *args, **kwargs):
        self.invocations.append(('put_health', args, kwargs))
        return Response('Mock!')

    def delete(self, *args, **kwargs):
        self.invocations.append(('delete', args, kwargs))
        return Response('Mock!')


class MockRegistry_broken():
    def __init__(self):
        self.invocations = []

    class RegistryUnavailable(Exception):
        pass

    def put(self, *args, **kwargs):
        self.invocations.append(('put', args, kwargs))
        raise self.RegistryUnavailable

    def delete(self, *args, **kwargs):
        self.invocations.append(('delete', args, kwargs))
        raise self.RegistryUnavailable


class TestAggregatorAPI(unittest.TestCase):
    """An attempt to test AggregatorAPI - may not be the best way to do this. We mock out things where necessary."""

    def setUp(self):
        self.mock_log = MockLogger()
        self.mock_registry = MockRegistry()
        self.api = v1_0.Routes(logger=self.mock_log, registry=self.mock_registry)

    def test_add_resource(self):
        """Adding a resource calls 'put' on registry"""
        # note that we do not test return code, just that we call 'put'
        key = "17c27274-6aaf-4f4b-9b9a-5b5b5dc2af63"
        resource = {
            'type': 'node',
            'data': {
                'label': 'test',
                'href': 'http://127.0.0.1:8080',
                'version': '1442328230:920000000',
                'caps': {},
                'services': [],
                'id': key
            }
        }
        self.api._add_resource(json.dumps(resource))
        expected = [
            ('put',
                (u'nodes', u'' + key, '{{"version": "1442328230:920000000", "label": "test", "href": "http://127.0.0.1:8080", "@_apiversion": "v1.0", "services": [], "caps": {}, "id": "{}"}}'.format({}, key)),
                {'port': REGISTRY_PORT}),
            ('put_health', (key, int(time.time())), {'port': 4001, 'ttl': 12})
        ]
        self.assertEqual(expected, self.mock_registry.invocations)

    def test_add_resource_modification(self):
        """UUID should be modified to lower case before put"""
        key = "3B8BE755-08FF-452B-B217-C9151EB21193"
        resource = {
            'type': 'node',
            'data': {
                'label': 'test',
                'href': 'http://127.0.0.1:8080',
                'version': '1442328230:920000000',
                'caps': {},
                'services': [],
                'id': key
            }
        }
        self.api._add_resource(json.dumps(resource))
        expected = [
            ('put',
                (u'nodes', u'' + key.lower(), '{{"version": "1442328230:920000000", "label": "test", "href": "http://127.0.0.1:8080", "@_apiversion": "v1.0", "services": [], "caps": {}, "id": "{}"}}'.format({}, key.lower())),
                {'port': REGISTRY_PORT}),
            ('put_health', (key.lower(), int(time.time())), {'port': 4001, 'ttl': 12})
        ]
        self.assertEqual(expected, self.mock_registry.invocations)

    def test_add_resource_non_type(self):
        """Attempting to register resources of a non-supported type aborts"""
        with self.assertRaises(HTTPException) as cm:
            self.api._add_resource('{"type": "nonsense"}')
        self.assertEqual(400, cm.exception.code)
        self.assertEqual([], self.mock_registry.invocations)

    def test_add_resource_no_id(self):
        """Do not allow resources with no 'id' to be added"""
        with self.assertRaises(HTTPException) as cm:
            self.api._add_resource('{"type": "flow"}')
        self.assertEqual(400, cm.exception.code)
        self.assertEqual([], self.mock_registry.invocations)

    def test_delete_resource(self):
        """Adding a resource calls 'put' on registry"""
        # note that we do not test return code, just that we call 'put'
        self.api._delete("flow", "a")
        expected = [('delete', ('flow', 'a'), {'port': REGISTRY_PORT})]
        self.assertEqual(expected, self.mock_registry.invocations)


class TestAggregatorAPI_NoRegistry(unittest.TestCase):

    def setUp(self):
        self.mock_log = MockLogger()
        self.mock_registry = MockRegistry_broken()
        self.api = v1_0.Routes(logger=self.mock_log, registry=self.mock_registry)

    def test_add_resource_no_registry(self):
        """Return error if registry unavailable, and add no initial health check"""
        key = "17c27274-6aaf-4f4b-9b9a-5b5b5dc2af63"
        resource = {
            'type': 'node',
            'data': {
                'label': 'test',
                'href': 'http://127.0.0.1:8080',
                'version': '1442328230:920000000',
                'caps': {},
                'services': [],
                'id': key
            }
        };
        with self.assertRaises(HTTPException) as cm:
            self.api._add_resource(json.dumps(resource))
        self.assertEqual(500, cm.exception.code)
        expected = [
            ('put',
                (u'nodes', u'' + key, '{{"version": "1442328230:920000000", "label": "test", "href": "http://127.0.0.1:8080", "@_apiversion": "v1.0", "services": [], "caps": {}, "id": "{}"}}'.format({}, key)),
                {'port': REGISTRY_PORT})
        ]
        self.assertEqual(expected, self.mock_registry.invocations)

    def test_delete_resource_no_registry(self):
        """Return error if registry unavailable"""
        with self.assertRaises(HTTPException) as cm:
            self.api._delete("flow", "a")
        self.assertEqual(500, cm.exception.code)
        expected = [('delete', ('flow', 'a'), {'port': REGISTRY_PORT})]
        self.assertEqual(expected, self.mock_registry.invocations)
